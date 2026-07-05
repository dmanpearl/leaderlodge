from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.dateparse import parse_date

from leaderlodge.core.decorators import demo_or_login_required
from leaderlodge.games.forms import (
    GameRecordForm,
    GameEditForm,
    parse_participants_from_post,
    prepare_participant_rows,
)
from leaderlodge.groups.player_search import roster_for_group
from leaderlodge.games.game_type_icons import game_type_icon_url
from leaderlodge.games.list_density import (
    game_list_date_format,
    resolve_game_list_density,
)
from leaderlodge.games.game_size import (
    available_game_sizes,
    game_size_filter_label,
    resolve_game_size,
)
from leaderlodge.games.list_stats import build_game_list_stats
from leaderlodge.games.list_table import build_game_list_table, show_weight_column
from leaderlodge.games.models import Game, GameParticipantResult
from leaderlodge.games.registry import (
    GAME_TYPES,
    ScoreType,
    game_type_choices,
    get_game_type,
    score_type_choices_for,
)
from leaderlodge.games.last_location import last_recorded_location_name
from leaderlodge.games.reuse_players import (
    previous_game_participant_rows,
    reuse_players_summary,
)
from leaderlodge.games.scoring import (
    default_participant_score_value,
    record_game_rules_summary,
)
from leaderlodge.games.matchup import build_matchup_view
from leaderlodge.insights.model_selection import preferred_insight_model_id
from leaderlodge.insights.registry import MODEL_REGISTRY
from leaderlodge.insights.views import insights_ui_enabled
from leaderlodge.games.services import ParticipantInput, record_game
from leaderlodge.games.score_changes import apply_game_edits, user_can_edit_game_scores
from leaderlodge.groups.models import Group, GroupPlayer, Location
from leaderlodge.groups.services import (
    can_edit_group,
    can_view_group,
    get_demo_group,
    single_user_group,
    visible_groups,
)
from leaderlodge.accounts.game_selection import (
    all_game_type_codes,
    persist_game_type_code,
    resolve_game_type_code,
)
from leaderlodge.accounts.group_selection import (
    persist_group_id,
    preferred_group_id,
    resolve_group_id,
)
from leaderlodge.groups.locations import locations_for_group, resolve_game_location
from leaderlodge.groups.teams import PLAYER_TYPE_CHOICES, normalize_player_type

GAMES_PER_PAGE = 25


def _game_list_params(request: HttpRequest) -> dict:
    sort = request.GET.get("sort", "desc")
    if sort not in ("asc", "desc"):
        sort = "desc"
    group = request.GET.get("group") if "group" in request.GET else None
    if group is not None:
        group = group.strip()
    return {
        "group": group,
        "game_type": request.GET.get("game_type", "").strip(),
        "player": request.GET.get("player", "").strip(),
        "player_type": normalize_player_type(request.GET.get("player_type", "")),
        "location": request.GET.get("location", "").strip(),
        "game_size": request.GET.get("game_size", "").strip(),
        "sort": sort,
    }


def _game_list_params_changed(raw: dict, resolved: dict[str, str]) -> bool:
    if raw["game_type"] != resolved["game_type"]:
        return True
    raw_group = raw["group"]
    if raw_group is None:
        return bool(resolved["group"])
    return raw_group != resolved["group"]


def _resolve_game_list_params(
    request: HttpRequest,
    params: dict,
    groups,
) -> dict[str, str]:
    resolved = {
        "group": resolve_group_id(
            request,
            requested=params["group"],
            available_groups=groups,
        ),
        "game_type": resolve_game_type_code(
            request,
            requested=params["game_type"],
            available_codes=all_game_type_codes(),
        ),
        "player": params["player"],
        "player_type": params.get("player_type", ""),
        "location": params["location"],
        "game_size": params["game_size"],
        "sort": params["sort"],
    }
    return resolved


def _game_list_redirect_query(params: dict[str, str], page: str | None) -> str:
    from urllib.parse import urlencode

    query_params = {key: value for key, value in params.items() if value}
    if page:
        query_params["page"] = page
    return urlencode(query_params)


def _games_queryset_for_filter_choices(user, params: dict[str, str]):
    games_qs = Game.objects.filter(group__in=visible_groups(user))
    if params["group"].isdigit():
        games_qs = games_qs.filter(group_id=int(params["group"]))
    if params["game_type"] in GAME_TYPES:
        games_qs = games_qs.filter(game_type_code=params["game_type"])
    return games_qs


def _filtered_games_queryset(user, params: dict[str, str]):
    games_qs = _games_queryset_for_filter_choices(user, params).select_related(
        "group", "recorded_by", "location"
    )

    if params["game_type"] not in GAME_TYPES:
        return games_qs.none()
    if params["location"].isdigit():
        games_qs = games_qs.filter(location_id=int(params["location"]))
    if params.get("player", "").isdigit():
        from django.db.models import Q

        player_id = int(params["player"])
        games_qs = games_qs.filter(
            Q(participant_results__player_id=player_id)
            | Q(participant_results__player__team_members__member_id=player_id)
        ).distinct()
    player_type = params.get("player_type", "")
    if player_type == "team":
        games_qs = games_qs.filter(participant_results__player__is_team=True).distinct()
    elif player_type == "people":
        games_qs = games_qs.filter(
            participant_results__player__is_team=False
        ).distinct()
    elif player_type == "user":
        games_qs = games_qs.filter(
            participant_results__player__is_team=False,
            participant_results__player__linked_user__isnull=False,
        ).distinct()
    elif player_type == "guest":
        games_qs = games_qs.filter(
            participant_results__player__is_team=False,
            participant_results__player__linked_user__isnull=True,
        ).distinct()
    if params.get("game_size", "").isdigit():
        games_qs = games_qs.filter(player_count=int(params["game_size"]))

    if params["sort"] == "asc":
        return games_qs.order_by("played_on", "created_at")
    return games_qs.order_by("-played_on", "-created_at")


def _location_choices_for_game_list(user, params: dict[str, str]):
    games_qs = _games_queryset_for_filter_choices(user, params).filter(
        location__isnull=False,
    )
    location_ids = games_qs.values_list("location_id", flat=True).distinct()
    return Location.objects.filter(pk__in=location_ids).order_by("name")


def _player_choices_for_game_list(user, params: dict[str, str]):
    games_qs = _games_queryset_for_filter_choices(user, params)
    player_ids = (
        GameParticipantResult.objects.filter(game__in=games_qs)
        .values_list("player_id", flat=True)
        .distinct()
    )
    players_qs = GroupPlayer.objects.filter(pk__in=player_ids).select_related(
        "linked_user",
        "group",
    )
    if params["group"].isdigit():
        players_qs = players_qs.filter(group_id=int(params["group"]))
        return players_qs.order_by("display_name", "pk")
    return players_qs.order_by("group__name", "display_name", "pk")


def _game_size_choices_for_game_list(user, params: dict[str, str]):
    games_qs = _games_queryset_for_filter_choices(user, params)
    return available_game_sizes(games_qs)


def _sanitize_game_list_params(
    params: dict[str, str],
    locations,
    players,
    game_size_options,
) -> dict[str, str]:
    sanitized = dict(params)
    if sanitized["location"].isdigit():
        valid_ids = {location.pk for location in locations}
        if int(sanitized["location"]) not in valid_ids:
            sanitized["location"] = ""
    if sanitized["player"].isdigit():
        valid_ids = {player.pk for player in players}
        if int(sanitized["player"]) not in valid_ids:
            sanitized["player"] = ""
    if sanitized["game_size"].isdigit():
        if int(sanitized["game_size"]) not in game_size_options:
            sanitized["game_size"] = ""
    return sanitized


def _game_list_filter_query(params: dict[str, str]) -> str:
    from urllib.parse import urlencode

    return urlencode({key: value for key, value in params.items() if value})


def _game_list_has_filters(params: dict[str, str]) -> bool:
    return any(
        params[key]
        for key in ("group", "player", "player_type", "location", "game_size")
        if key != "player_type" or params[key]
    )


def _game_list_filter_summary(
    *,
    params: dict[str, str],
    groups,
    players,
    locations,
) -> str:
    labels: list[str] = []

    if params["group"].isdigit():
        group_id = int(params["group"])
        for group in groups:
            if group.pk == group_id:
                labels.append(group.name)
                break

    if params["player"].isdigit():
        player_id = int(params["player"])
        for player in players:
            if player.pk == player_id:
                labels.append(player.display_label)
                break

    from leaderlodge.groups.teams import player_type_filter_label

    type_label = player_type_filter_label(params.get("player_type", ""))
    if type_label:
        labels.append(type_label)

    if params["location"].isdigit():
        location_id = int(params["location"])
        for location in locations:
            if location.pk == location_id:
                labels.append(location.name)
                break

    if params["game_size"].isdigit():
        labels.append(game_size_filter_label(int(params["game_size"])))

    return ", ".join(labels)


def _resolve_row_player(group, player_id_raw: str, guest_name: str):
    player = None
    display_label = ""
    if player_id_raw.strip():
        player = (
            group.players.filter(pk=player_id_raw.strip(), is_active=True)
            .select_related("linked_user")
            .first()
        )
        if player is not None:
            display_label = player.display_label
    elif guest_name.strip():
        display_label = guest_name.strip()
        player = group.players.filter(
            display_name__iexact=display_label,
            is_active=True,
        ).first()
    return player, display_label


def _participant_rows_from_post(group, post):
    rows = []
    player_ids = post.getlist("participant_player_id")
    guest_names = post.getlist("participant_guest_name")
    teammate_player_ids = post.getlist("participant_teammate_player_id")
    teammate_guest_names = post.getlist("participant_teammate_guest_name")
    scores = post.getlist("participant_score")
    while len(teammate_player_ids) < len(player_ids):
        teammate_player_ids.append("")
    while len(teammate_guest_names) < len(player_ids):
        teammate_guest_names.append("")

    for (
        player_id_raw,
        guest_name,
        teammate_player_id_raw,
        teammate_guest_name,
        score_raw,
    ) in zip(
        player_ids,
        guest_names,
        teammate_player_ids,
        teammate_guest_names,
        scores,
        strict=False,
    ):
        player, display_label = _resolve_row_player(group, player_id_raw, guest_name)
        if not display_label:
            continue
        teammate, teammate_label = _resolve_row_player(
            group, teammate_player_id_raw, teammate_guest_name
        )
        side_label = display_label
        if teammate_label:
            labels = sorted(
                [display_label, teammate_label], key=lambda value: value.lower()
            )
            side_label = "+".join(labels)

        rows.append(
            {
                "player": player,
                "player_id": player.pk if player else "",
                "guest_name": guest_name.strip() if not player_id_raw.strip() else "",
                "teammate_player_id": teammate.pk if teammate else "",
                "teammate_guest_name": (
                    teammate_guest_name.strip()
                    if teammate_label and not teammate_player_id_raw.strip()
                    else ""
                ),
                "teammate_display_label": teammate_label,
                "display_label": side_label,
                "played": True,
                "score": score_raw,
            }
        )
    return rows


def _single_user_group(user) -> Group | None:
    return single_user_group(user)


def _requested_game_type_code(request: HttpRequest) -> str:
    return (
        request.GET.get("game_type_code", "").strip()
        or request.GET.get("game_type", "").strip()
    )


def _reuse_lookup_codes(form: GameRecordForm) -> tuple[Group, str] | None:
    """Group and game type submitted with reuse_roster / load_roster."""
    if not form.is_valid():
        return None
    group = form.cleaned_data.get("group")
    game_type_code = form.cleaned_data.get("game_type_code")
    if group is None or not game_type_code or game_type_code not in GAME_TYPES:
        return None
    return group, game_type_code


def _resolve_group(request: HttpRequest, form: GameRecordForm) -> Group | None:
    raw_id = request.POST.get("group") or request.GET.get("group")
    if raw_id:
        return Group.objects.filter(pk=raw_id).first()
    if form.is_bound and form.is_valid():
        return form.cleaned_data.get("group")
    return None


def _played_on_value_and_display(form: GameRecordForm) -> tuple[str, str]:
    raw = None
    if form.is_bound and form.data.get("played_on"):
        raw = form.data.get("played_on")
    elif form.initial.get("played_on") is not None:
        raw = form.initial.get("played_on")

    if raw is None:
        return "", ""

    value = raw.isoformat() if hasattr(raw, "isoformat") else str(raw)
    parsed = parse_date(value)
    if parsed:
        display = parsed.strftime("%b %d, %Y").replace(" 0", " ")
    else:
        display = value
    return value, display


@demo_or_login_required
def game_list(request: HttpRequest) -> HttpResponse:
    groups = visible_groups(request.user).order_by("name")
    params = _game_list_params(request)
    resolved_params = _resolve_game_list_params(request, params, groups)
    if _game_list_params_changed(params, resolved_params):
        query = _game_list_redirect_query(resolved_params, request.GET.get("page"))
        url = reverse("games:list")
        if query:
            url = f"{url}?{query}"
        return redirect(url)

    params = resolved_params
    locations = _location_choices_for_game_list(request.user, params)
    players = _player_choices_for_game_list(request.user, params)
    game_size_options = _game_size_choices_for_game_list(request.user, params)
    params = _sanitize_game_list_params(params, locations, players, game_size_options)
    games_qs = _filtered_games_queryset(request.user, params)
    selected_game_type = get_game_type(params["game_type"])
    list_stats = build_game_list_stats(
        games_qs=games_qs,
        game_type_code=params["game_type"],
        player_type=params.get("player_type", ""),
    )
    paginator = Paginator(games_qs, GAMES_PER_PAGE)
    page = paginator.get_page(request.GET.get("page"))
    games = list(page.object_list)
    player_columns, game_rows = build_game_list_table(games)
    stats_player_count = len(list_stats.players) if list_stats else 0
    list_density = resolve_game_list_density(
        table_player_count=len(player_columns),
        stats_player_count=stats_player_count,
    )

    groups = visible_groups(request.user).order_by("name")
    has_any_games = Game.objects.filter(group__in=groups).exists()

    return render(
        request,
        "games/game_list.html",
        {
            "page": page,
            "game_rows": game_rows,
            "player_columns": player_columns,
            "list_stats": list_stats,
            "list_density": list_density,
            "date_format": game_list_date_format(list_density),
            "params": params,
            "filter_query": _game_list_filter_query(params),
            "has_filters": _game_list_has_filters(params),
            "filter_summary": _game_list_filter_summary(
                params=params,
                groups=groups,
                players=players,
                locations=locations,
            ),
            "show_empty_filters_message": has_any_games,
            "groups": groups,
            "game_types": game_type_choices(),
            "player_type_choices": PLAYER_TYPE_CHOICES,
            "locations": locations,
            "players": players,
            "game_size_options": game_size_options,
            "selected_game_size": (
                int(params["game_size"]) if params["game_size"].isdigit() else None
            ),
            "selected_game_type": selected_game_type,
            "selected_game_type_icon_url": game_type_icon_url(params["game_type"]),
            "show_group_column": not params["group"],
            "show_weight_column": show_weight_column(
                games=games,
                game_type_code=params["game_type"],
            ),
            "show_location_column": not params["location"],
        },
    )


@demo_or_login_required
def game_create(request: HttpRequest) -> HttpResponse:
    show_roster = False
    participant_error = None
    post_for_rows = None
    reused_participant_rows = None
    game_type = None

    if request.method == "POST":
        form = GameRecordForm(request.POST, user=request.user)
        action = request.POST.get("action")
        if action == "save":
            show_roster = True
            post_for_rows = request.POST
        elif (
            action in ("load_roster", "reuse_roster")
            and form.is_valid()
            and request.user.is_authenticated
        ):
            lookup = _reuse_lookup_codes(form)
            if lookup is None:
                show_roster = False
            else:
                group, game_type_code = lookup
                if action == "reuse_roster":
                    reused_participant_rows = previous_game_participant_rows(
                        group, game_type_code
                    )
                    if not reused_participant_rows:
                        messages.info(
                            request,
                            "No previous game found for this group and game type.",
                        )
                    else:
                        show_roster = True
                else:
                    show_roster = True
                if show_roster:
                    persist_game_type_code(request, game_type_code)
                    persist_group_id(request, group.pk)
    else:
        initial = {}
        if request.GET.get("group"):
            initial["group"] = request.GET.get("group")
        elif preferred_group_id(request):
            initial["group"] = preferred_group_id(request)
        elif request.user.is_authenticated:
            single = _single_user_group(request.user)
            if single:
                initial["group"] = single.pk
        elif not request.user.is_authenticated:
            demo = get_demo_group()
            if demo is not None:
                initial["group"] = demo.pk
        initial["game_type_code"] = resolve_game_type_code(
            request,
            requested=_requested_game_type_code(request),
            available_codes=all_game_type_codes(),
        )
        form = GameRecordForm(user=request.user, initial=initial)

    group = _resolve_group(request, form)
    if request.method == "POST" and group:
        action = request.POST.get("action")
        if action in ("load_roster", "reuse_roster", "save") and not can_edit_group(
            request.user, group
        ):
            raise Http404
    if show_roster and group and not can_edit_group(request.user, group):
        raise Http404

    if show_roster and group:
        if (
            form.is_bound
            and form.is_valid()
            and form.cleaned_data.get("game_type_code")
        ):
            game_type_code = form.cleaned_data["game_type_code"]
        else:
            game_type_code = request.POST.get("game_type_code")
        game_type = get_game_type(game_type_code)

    roster = []
    participant_rows = []
    if group and show_roster:
        roster = roster_for_group(group)
        if post_for_rows is not None:
            participant_rows = _participant_rows_from_post(group, post_for_rows)
        elif reused_participant_rows is not None:
            participant_rows = reused_participant_rows

    if request.method == "POST" and request.POST.get("action") == "save" and group:
        if not request.user.is_authenticated:
            raise Http404
        save_form = GameRecordForm(
            {
                "group": request.POST.get("group"),
                "game_type_code": request.POST.get("game_type_code"),
                "played_on": request.POST.get("played_on"),
                "location_name": request.POST.get("location_name", ""),
            },
            user=request.user,
        )
        if save_form.is_valid():
            rows = parse_participants_from_post(request.POST, group=group)
            try:
                prepare_participant_rows(rows, save_form.cleaned_data["game_type_code"])
                location = resolve_game_location(
                    group=group,
                    location_name=save_form.cleaned_data.get("location_name", ""),
                )
                participants = [
                    ParticipantInput(
                        player=row["player"],
                        score=row["score"],
                        result=row["result"],
                        placement=row["placement"],
                    )
                    for row in rows
                ]
                game = record_game(
                    user=request.user,
                    group=group,
                    game_type_code=save_form.cleaned_data["game_type_code"],
                    played_on=save_form.cleaned_data["played_on"],
                    participants=participants,
                    location=location,
                    score_type=request.POST.get("score_type", ""),
                )
            except ValidationError as exc:
                participant_error = (
                    exc.messages[0] if getattr(exc, "messages", None) else str(exc)
                )
                game_type = get_game_type(save_form.cleaned_data["game_type_code"])
                form = save_form
                participant_rows = _participant_rows_from_post(group, request.POST)
            else:
                persist_game_type_code(
                    request,
                    save_form.cleaned_data["game_type_code"],
                )
                persist_group_id(request, group.pk)
                messages.success(request, "Game recorded.")
                return redirect("games:detail", pk=game.pk)

    played_on_value = ""
    played_on_display = ""
    location_name = ""
    score_type = ScoreType.TRADITIONAL.value
    selected_setup_game_type_code = ""
    if form.is_bound:
        selected_setup_game_type_code = (form.data.get("game_type_code") or "").strip()
    else:
        initial_code = form.initial.get("game_type_code")
        if initial_code:
            selected_setup_game_type_code = str(initial_code).strip()
    setup_game_type_options = [
        (code, name, game_type_icon_url(code)) for code, name in game_type_choices()
    ]
    selected_setup_game_type_icon_url = (
        game_type_icon_url(selected_setup_game_type_code)
        if selected_setup_game_type_code in GAME_TYPES
        else ""
    )
    if show_roster and group:
        played_on_value, played_on_display = _played_on_value_and_display(form)
        if form.is_bound:
            location_name = form.data.get("location_name", "")
            score_type = request.POST.get("score_type", score_type)
        elif form.initial.get("location_name"):
            location_name = form.initial.get("location_name", "")

    return render(
        request,
        "games/game_form.html",
        {
            "form": form,
            "group": group,
            "participant_rows": participant_rows,
            "roster": roster,
            "game_rules_summary": (
                record_game_rules_summary(game_type.code) if game_type else ""
            ),
            "game_type": game_type,
            "score_type_choices": (
                score_type_choices_for(game_type.code) if game_type else []
            ),
            "score_type": score_type,
            "show_roster": show_roster and group is not None and game_type is not None,
            "participant_error": participant_error,
            "played_on_value": played_on_value,
            "played_on_display": played_on_display,
            "location_name": location_name,
            "setup_game_type_options": setup_game_type_options,
            "selected_setup_game_type_code": selected_setup_game_type_code,
            "selected_setup_game_type_icon_url": selected_setup_game_type_icon_url,
            "default_participant_score": (
                default_participant_score_value(game_type.code) if game_type else ""
            ),
        },
    )


@login_required
def game_reuse_preview(request: HttpRequest) -> JsonResponse:
    group_id = request.GET.get("group", "").strip()
    game_type_code = _requested_game_type_code(request)
    if not group_id.isdigit() or game_type_code not in GAME_TYPES:
        return JsonResponse(
            {
                "available": False,
                "summary": "",
                "labels": [],
                "last_location_name": "",
            }
        )

    group = Group.objects.filter(pk=int(group_id)).first()
    if group is None or not can_edit_group(request.user, group):
        raise Http404

    payload = reuse_players_summary(group, game_type_code)
    payload["last_location_name"] = last_recorded_location_name(
        request.user, game_type_code
    )
    return JsonResponse(payload)


@demo_or_login_required
def game_matchup(request: HttpRequest) -> HttpResponse:
    game_id = request.GET.get("game")
    if not game_id:
        raise Http404

    game = get_object_or_404(
        Game.objects.select_related(
            "group", "location", "recorded_by"
        ).prefetch_related("participant_results__player__linked_user"),
        pk=game_id,
    )
    if not can_view_group(request.user, game.group):
        raise Http404

    matchup = build_matchup_view(game)
    insights_enabled = insights_ui_enabled()
    return render(
        request,
        "games/matchup.html",
        {
            "matchup": matchup,
            "game": game,
            "game_type": get_game_type(game.game_type_code),
            "is_double": game.double_weight == 2,
            "is_half": game.half_weight == 2,
            "insights_enabled": insights_enabled,
            "insight_models": tuple(MODEL_REGISTRY.values()),
            "selected_insight_model": preferred_insight_model_id(request),
        },
    )


def game_detail(request: HttpRequest, pk: int) -> HttpResponse:
    game = get_object_or_404(
        Game.objects.select_related(
            "group", "recorded_by", "location"
        ).prefetch_related("participant_results__player"),
        pk=pk,
    )
    if not can_view_group(request.user, game.group):
        raise Http404

    game_type = get_game_type(game.game_type_code)
    results = game.participant_results.order_by("placement", "pk")

    return render(
        request,
        "games/game_detail.html",
        {
            "game": game,
            "game_type": game_type,
            "game_type_icon_url": game_type_icon_url(game.game_type_code),
            "results": results,
            "is_double": game.double_weight == 2,
            "is_half": game.half_weight == 2,
            "insights_enabled": insights_ui_enabled(),
            "insight_models": tuple(MODEL_REGISTRY.values()),
            "selected_insight_model": preferred_insight_model_id(request),
            "can_edit_game": user_can_edit_game_scores(request.user),
        },
    )


@login_required
def game_edit_game(request: HttpRequest, pk: int) -> HttpResponse:
    if not user_can_edit_game_scores(request.user):
        raise Http404

    game = get_object_or_404(
        Game.objects.select_related("group", "location").prefetch_related(
            "participant_results__player"
        ),
        pk=pk,
    )
    if not can_view_group(request.user, game.group):
        raise Http404

    game_type = get_game_type(game.game_type_code)
    if request.method == "POST":
        form = GameEditForm(request.POST, game=game)
        if form.is_valid():
            try:
                summary = apply_game_edits(
                    game=game,
                    user=request.user,
                    notes=form.cleaned_data["notes"],
                    score_updates=form.score_updates(),
                    new_location=form.resolved_location(),
                    new_played_on=form.cleaned_data["played_on"],
                )
            except ValidationError as exc:
                messages.error(request, str(exc))
            else:
                if summary.logs:
                    messages.success(request, "Game updated.")
                    return redirect("games:detail", pk=game.pk)
                messages.warning(request, "No changes were made.")
    else:
        form = GameEditForm(game=game)

    return render(
        request,
        "games/game_edit.html",
        {
            "game": game,
            "game_type": game_type,
            "game_type_icon_url": game_type_icon_url(game.game_type_code),
            "form": form,
            "results": game.participant_results.order_by("placement", "pk"),
            "is_double": game.double_weight == 2,
        },
    )
