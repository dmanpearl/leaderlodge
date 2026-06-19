from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.dateparse import parse_date

from leaderlodge.games.forms import (
    GameRecordForm,
    parse_participants_from_post,
    prepare_participant_rows,
)
from leaderlodge.groups.player_search import roster_for_group
from leaderlodge.games.list_density import game_list_date_format, resolve_game_list_density
from leaderlodge.games.list_stats import build_game_list_stats
from leaderlodge.games.list_table import build_game_list_table, show_weight_column
from leaderlodge.games.models import Game, GameParticipantResult
from leaderlodge.games.registry import GAME_TYPES, game_type_choices, get_game_type
from leaderlodge.games.scoring import scoring_instructions
from leaderlodge.games.services import ParticipantInput, record_game
from leaderlodge.groups.models import Group, GroupPlayer, Location
from leaderlodge.groups.services import (
    single_user_group,
    user_groups,
    user_is_member,
)
from leaderlodge.groups.locations import locations_for_group, resolve_game_location

GAMES_PER_PAGE = 25


def _game_list_params(request: HttpRequest) -> dict[str, str]:
    sort = request.GET.get("sort", "desc")
    if sort not in ("asc", "desc"):
        sort = "desc"
    return {
        "group": request.GET.get("group", "").strip(),
        "game_type": request.GET.get("game_type", "").strip(),
        "player": request.GET.get("player", "").strip(),
        "location": request.GET.get("location", "").strip(),
        "sort": sort,
    }


def _default_game_type_code(
    user,
    *,
    group_id: str,
    requested: str,
) -> str:
    if requested in GAME_TYPES:
        return requested

    games_qs = Game.objects.filter(group__in=user_groups(user))
    if group_id.isdigit():
        games_qs = games_qs.filter(group_id=int(group_id))
    code = (
        games_qs.values_list("game_type_code", flat=True)
        .distinct()
        .order_by("game_type_code")
        .first()
    )
    if code in GAME_TYPES:
        return code
    return game_type_choices()[0][0]


def _resolve_game_list_params(user, params: dict[str, str]) -> dict[str, str]:
    resolved = dict(params)
    resolved["game_type"] = _default_game_type_code(
        user,
        group_id=params["group"],
        requested=params["game_type"],
    )
    return resolved


def _game_list_redirect_query(params: dict[str, str], page: str | None) -> str:
    from urllib.parse import urlencode

    query_params = {key: value for key, value in params.items() if value}
    if page:
        query_params["page"] = page
    return urlencode(query_params)


def _games_queryset_for_filter_choices(user, params: dict[str, str]):
    games_qs = Game.objects.filter(group__in=user_groups(user))
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
    if params["player"].isdigit():
        games_qs = games_qs.filter(
            participant_results__player_id=int(params["player"]),
        ).distinct()

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


def _sanitize_game_list_params(
    params: dict[str, str],
    locations,
    players,
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
    return sanitized


def _game_list_filter_query(params: dict[str, str]) -> str:
    from urllib.parse import urlencode

    return urlencode({key: value for key, value in params.items() if value})


def _game_list_has_filters(params: dict[str, str]) -> bool:
    return any(params[key] for key in ("group", "player", "location"))


def _participant_rows_from_post(group, post):
    rows = []
    player_ids = post.getlist("participant_player_id")
    guest_names = post.getlist("participant_guest_name")
    scores = post.getlist("participant_score")
    for player_id_raw, guest_name, score_raw in zip(
        player_ids, guest_names, scores, strict=False
    ):
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

        if not display_label:
            continue

        rows.append(
            {
                "player": player,
                "player_id": player.pk if player else "",
                "guest_name": guest_name.strip() if not player_id_raw.strip() else "",
                "display_label": display_label,
                "played": True,
                "score": score_raw,
            }
        )
    return rows


def _single_user_group(user) -> Group | None:
    return single_user_group(user)


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


@login_required
def game_list(request: HttpRequest) -> HttpResponse:
    params = _game_list_params(request)
    resolved_params = _resolve_game_list_params(request.user, params)
    if resolved_params["game_type"] != params["game_type"]:
        query = _game_list_redirect_query(resolved_params, request.GET.get("page"))
        url = reverse("games:list")
        if query:
            url = f"{url}?{query}"
        return redirect(url)

    params = resolved_params
    locations = _location_choices_for_game_list(request.user, params)
    players = _player_choices_for_game_list(request.user, params)
    params = _sanitize_game_list_params(params, locations, players)
    games_qs = _filtered_games_queryset(request.user, params)
    selected_game_type = get_game_type(params["game_type"])
    list_stats = build_game_list_stats(
        games_qs=games_qs,
        game_type_code=params["game_type"],
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

    groups = user_groups(request.user).order_by("name")
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
            "show_empty_filters_message": has_any_games,
            "groups": groups,
            "game_types": game_type_choices(),
            "locations": locations,
            "players": players,
            "selected_game_type": selected_game_type,
            "show_group_column": not params["group"],
            "show_weight_column": show_weight_column(
                games=games,
                game_type_code=params["game_type"],
            ),
            "show_location_column": not params["location"],
        },
    )


@login_required
def game_create(request: HttpRequest) -> HttpResponse:
    show_roster = False
    participant_error = None
    post_for_rows = None
    game_type = None

    if request.method == "POST":
        form = GameRecordForm(request.POST, user=request.user)
        action = request.POST.get("action")
        if action == "save":
            show_roster = True
            post_for_rows = request.POST
        elif action == "load_roster" and form.is_valid():
            show_roster = True
    else:
        initial = {}
        if request.GET.get("group"):
            initial["group"] = request.GET.get("group")
        elif not request.GET.get("setup"):
            single = _single_user_group(request.user)
            if single:
                initial["group"] = single.pk
        form = GameRecordForm(user=request.user, initial=initial)

    group = _resolve_group(request, form)
    if group and not user_is_member(request.user, group):
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

    if request.method == "POST" and request.POST.get("action") == "save" and group:
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
                )
            except ValidationError as exc:
                participant_error = (
                    exc.messages[0] if getattr(exc, "messages", None) else str(exc)
                )
                game_type = get_game_type(save_form.cleaned_data["game_type_code"])
                form = save_form
                participant_rows = _participant_rows_from_post(group, request.POST)
            else:
                messages.success(request, "Game recorded.")
                return redirect("games:detail", pk=game.pk)

    played_on_value = ""
    played_on_display = ""
    location_name = ""
    if show_roster and group:
        played_on_value, played_on_display = _played_on_value_and_display(form)
        if form.is_bound:
            location_name = form.data.get("location_name", "")
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
            "scoring_instructions": (
                scoring_instructions(game_type.code) if game_type else ""
            ),
            "game_type": game_type,
            "show_roster": show_roster and group is not None and game_type is not None,
            "participant_error": participant_error,
            "played_on_value": played_on_value,
            "played_on_display": played_on_display,
            "location_name": location_name,
        },
    )


@login_required
def game_detail(request: HttpRequest, pk: int) -> HttpResponse:
    game = get_object_or_404(
        Game.objects.select_related("group", "recorded_by", "location").prefetch_related(
            "participant_results__player"
        ),
        pk=pk,
    )
    if not user_is_member(request.user, game.group):
        raise Http404

    game_type = get_game_type(game.game_type_code)
    results = game.participant_results.order_by("placement", "pk")

    return render(
        request,
        "games/game_detail.html",
        {
            "game": game,
            "game_type": game_type,
            "results": results,
            "is_double": game.double_weight == 2,
            "is_half": game.half_weight == 2,
        },
    )
