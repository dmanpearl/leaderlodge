import json
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST

from leaderlodge.core.decorators import demo_or_login_required
from leaderlodge.core.models import SiteSettings
from leaderlodge.groups.names import apply_label_overrides, disambiguate_labels
from leaderlodge.games.ai_entry_copy import ai_entry_example, ai_entry_help_content
from leaderlodge.games.forms import (
    GameRecordForm,
    GameEditForm,
    parse_participants_from_post,
    prepare_participant_rows,
)
from leaderlodge.games.reuse_players import participant_rows_for_edit_game
from leaderlodge.games.roster_suggestions import (
    suggest_lineup_entries,
    suggest_side_entries,
)
from leaderlodge.groups.player_search import roster_for_group
from leaderlodge.games.features import (
    apply_feature_selections_to_games_qs,
    leaderboard_filter_rows,
    resolve_feature_selections,
)
from leaderlodge.games.game_type_icons import (
    game_type_icon_url,
    score_type_icon_url,
    shutout_icon_url,
)
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
from leaderlodge.games.features import (
    record_game_feature_fields,
    record_game_kwargs_from_post,
    resolve_record_game_feature_values,
)
from leaderlodge.games.registry import (
    GAME_TYPES,
    game_type_choices,
    game_type_has_score_type,
    get_game_type,
    score_type_choices_for,
    score_type_label,
)
from leaderlodge.games.location_field import (
    location_geo_from_form,
    location_geo_post_values,
)
from leaderlodge.games.last_location import (
    last_recorded_location_name,
    last_recorded_score_type,
)
from leaderlodge.games.reuse_players import (
    participant_rows_from_game,
    previous_game_participant_rows,
    reuse_players_summary,
)
from leaderlodge.games.scoring import (
    default_participant_score_value,
    lineup_is_no_score_tie,
    no_score_tie_requested,
    record_game_rules_summary,
)
from leaderlodge.games.matchup import build_matchup_view
from leaderlodge.insights.model_selection import preferred_insight_model_id
from leaderlodge.insights.registry import MODEL_REGISTRY
from leaderlodge.insights.views import insights_ui_enabled
from leaderlodge.games.services import ParticipantInput, record_game
from leaderlodge.games.score_changes import (
    apply_game_edits,
    delete_game,
    user_can_edit_game,
)
from leaderlodge.groups.models import Group, GroupPlayer, Location
from leaderlodge.groups.services import (
    can_assign_location_place,
    can_edit_group,
    can_manage_group_members,
    can_view_group,
    get_demo_group,
    single_user_group,
    visible_groups,
)
from leaderlodge.accounts.game_selection import (
    available_game_type_codes,
    is_game_type_locked,
    persist_game_type_code,
    preferred_game_type_code,
    requested_game_type_token,
    resolve_game_type_code,
)
from leaderlodge.accounts.group_selection import (
    persist_group_id,
    preferred_group_id,
    resolve_group_id,
)
from leaderlodge.groups.locations import locations_for_group, resolve_game_location
from leaderlodge.groups.teams import PLAYER_TYPE_CHOICES, normalize_player_type
from leaderlodge.accounts.email_verification import is_email_verified

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
        "game_type": requested_game_type_token(request),
        "player": request.GET.get("player", "").strip(),
        "player_type": normalize_player_type(request.GET.get("player_type", "")),
        "location": request.GET.get("location", "").strip(),
        "game_size": request.GET.get("game_size", "").strip(),
        "year": request.GET.get("year", "").strip(),
        "month": request.GET.get("month", "").strip(),
        "period_preset": request.GET.get("period_preset", "").strip(),
        "start_date": request.GET.get("start_date", "").strip(),
        "end_date": request.GET.get("end_date", "").strip(),
        "shutout": request.GET.get("shutout", "").strip(),
        "score_type": request.GET.get("score_type", "").strip(),
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
            session=request.session,
        ),
        "game_type": resolve_game_type_code(
            request,
            requested=params["game_type"],
            available_codes=available_game_type_codes(request),
        ),
        "player": params["player"],
        "player_type": params.get("player_type", ""),
        "location": params["location"],
        "game_size": params["game_size"],
        "year": params.get("year", ""),
        "month": params.get("month", ""),
        "period_preset": params.get("period_preset", ""),
        "start_date": params.get("start_date", ""),
        "end_date": params.get("end_date", ""),
        "shutout": params.get("shutout", ""),
        "score_type": params.get("score_type", ""),
        "sort": params["sort"],
    }
    return resolved


def _game_list_redirect_query(params: dict[str, str], page: str | None) -> str:
    from urllib.parse import urlencode

    query_params = {}
    for key, value in params.items():
        if not value:
            continue
        if key == "game_type":
            query_params["type"] = value
        else:
            query_params[key] = value
    if page:
        query_params["page"] = page
    return urlencode(query_params)


def _games_queryset_for_filter_choices(user, params: dict[str, str], session=None):
    games_qs = Game.objects.filter(group__in=visible_groups(user, session=session))
    if params["group"].isdigit():
        games_qs = games_qs.filter(group_id=int(params["group"]))
    if params["game_type"] in GAME_TYPES:
        games_qs = games_qs.filter(game_type_code=params["game_type"])
    return games_qs


def _game_list_period(params: dict[str, str], groups):
    from leaderlodge.leaderboards.period import (
        LeaderboardPeriod,
        PERIOD_PRESET_CHOICES,
        period_filter_context,
    )

    if (
        not params.get("group", "").isdigit()
        or params.get("game_type") not in GAME_TYPES
    ):
        empty = LeaderboardPeriod.all_time()
        return empty, {
            "selected_period": empty,
            "period_year_options": [],
            "period_month_options": [],
            "period_preset_choices": PERIOD_PRESET_CHOICES,
            "period_show_custom_dates": (
                (params.get("period_preset") or "") == "custom"
            ),
            "period_label": "",
        }

    group = next(
        (item for item in groups if str(item.pk) == params["group"]),
        None,
    )
    if group is None:
        group = Group.objects.filter(pk=int(params["group"])).first()
    period_ctx = period_filter_context(
        group=group,
        game_type_code=params["game_type"],
        raw_year=params.get("year", ""),
        raw_month=params.get("month", ""),
        raw_preset=params.get("period_preset", ""),
        raw_start_date=params.get("start_date", ""),
        raw_end_date=params.get("end_date", ""),
    )
    return period_ctx["selected_period"], period_ctx


def _apply_period_params(params: dict[str, str], period) -> dict[str, str]:
    updated = dict(params)
    for key in ("year", "month", "period_preset", "start_date", "end_date"):
        updated[key] = ""
    updated.update(period.query_params())
    # Keep custom UI open when user chose custom but has not applied dates yet.
    if params.get("period_preset") == "custom" and not period.is_filtered:
        updated["period_preset"] = "custom"
    return updated


def _filtered_games_queryset(user, params: dict[str, str], period=None, session=None):
    from leaderlodge.leaderboards.period import (
        LeaderboardPeriod,
        filter_results_by_period,
        resolve_leaderboard_period_from_mapping,
        available_leaderboard_periods,
    )

    games_qs = _games_queryset_for_filter_choices(
        user, params, session=session
    ).select_related("group", "recorded_by", "location")

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

    if period is None:
        years: list[int] = []
        months_by_year: dict[int, tuple[int, ...]] = {}
        if params.get("group", "").isdigit() and params["game_type"] in GAME_TYPES:
            group = Group.objects.filter(pk=int(params["group"])).first()
            if group is not None:
                years, months_by_year = available_leaderboard_periods(
                    group, params["game_type"]
                )
        period = resolve_leaderboard_period_from_mapping(
            params,
            available_years=years,
            months_by_year=months_by_year,
        )
    if isinstance(period, LeaderboardPeriod) and period.is_filtered:
        games_qs = filter_results_by_period(games_qs, period, game_prefix="")

    from leaderlodge.leaderboards.game_filters import apply_shutout_filter_to_games_qs

    if params.get("shutout") in ("1", "true", "on"):
        games_qs = apply_shutout_filter_to_games_qs(
            games_qs,
            game_type_code=params["game_type"],
            shutout_only=True,
        )

    feature_selections = resolve_feature_selections(
        params, game_type_code=params["game_type"]
    )
    games_qs = apply_feature_selections_to_games_qs(
        games_qs,
        feature_selections,
        game_type_code=params["game_type"],
    )

    if params["sort"] == "asc":
        return games_qs.order_by("played_on", "created_at")
    return games_qs.order_by("-played_on", "-created_at")


def _location_choices_for_game_list(user, params: dict[str, str], session=None):
    games_qs = _games_queryset_for_filter_choices(user, params, session=session).filter(
        location__isnull=False,
    )
    location_ids = games_qs.values_list("location_id", flat=True).distinct()
    return Location.objects.filter(pk__in=location_ids).order_by("name")


def _player_choices_for_game_list(user, params: dict[str, str], session=None):
    games_qs = _games_queryset_for_filter_choices(user, params, session=session)
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


def _game_size_choices_for_game_list(user, params: dict[str, str], session=None):
    games_qs = _games_queryset_for_filter_choices(user, params, session=session)
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
    if sanitized.get("score_type"):
        valid = {
            value for value, _label in score_type_choices_for(sanitized["game_type"])
        }
        if sanitized["score_type"] not in valid:
            sanitized["score_type"] = ""
    elif "score_type" not in sanitized:
        sanitized["score_type"] = ""
    return sanitized


def _game_list_filter_query(params: dict[str, str]) -> str:
    from urllib.parse import urlencode

    query_params = {}
    for key, value in params.items():
        if not value:
            continue
        if key == "game_type":
            query_params["type"] = value
        else:
            query_params[key] = value
    return urlencode(query_params)


def _game_list_has_filters(params: dict[str, str]) -> bool:
    return any(
        params[key]
        for key in (
            "group",
            "player",
            "player_type",
            "location",
            "game_size",
            "year",
            "month",
            "period_preset",
            "start_date",
            "end_date",
            "shutout",
            "score_type",
        )
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

    if params.get("period_label"):
        labels.append(params["period_label"])

    if params.get("shutout") in ("1", "true", "on") and params.get("game_type"):
        from leaderlodge.games.registry import game_type_shutout_config

        config = game_type_shutout_config(params["game_type"])
        if config is not None:
            labels.append(config.label)

    if params.get("score_type") and params.get("game_type"):
        label = score_type_label(params["game_type"], params["score_type"])
        if label:
            labels.append(label)

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
        from leaderlodge.groups.player_search import resolve_typed_player_name

        display_label = guest_name.strip()
        player = resolve_typed_player_name(group=group, name=display_label)
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
    return requested_game_type_token(request)


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
    groups = visible_groups(request.user, session=request.session).order_by("name")
    params = _game_list_params(request)
    resolved_params = _resolve_game_list_params(request, params, groups)
    if _game_list_params_changed(params, resolved_params):
        query = _game_list_redirect_query(resolved_params, request.GET.get("page"))
        url = reverse("games:list")
        if query:
            url = f"{url}?{query}"
        return redirect(url)

    params = resolved_params
    groups = list(groups)
    selected_period, period_ctx = _game_list_period(params, groups)
    params = _apply_period_params(params, selected_period)
    locations = _location_choices_for_game_list(
        request.user, params, session=request.session
    )
    players = _player_choices_for_game_list(
        request.user, params, session=request.session
    )
    game_size_options = _game_size_choices_for_game_list(
        request.user, params, session=request.session
    )
    params = _sanitize_game_list_params(params, locations, players, game_size_options)
    games_qs = _filtered_games_queryset(
        request.user, params, period=selected_period, session=request.session
    )
    selected_game_type = get_game_type(params["game_type"])
    shutout_config = selected_game_type.shutout
    list_stats = build_game_list_stats(
        games_qs=games_qs,
        game_type_code=params["game_type"],
        player_type=params.get("player_type", ""),
    )
    paginator = Paginator(games_qs, GAMES_PER_PAGE)
    page = paginator.get_page(request.GET.get("page"))
    games = list(page.object_list)
    player_columns, game_rows = build_game_list_table(games)

    all_player_instances = (
        list(player_columns)
        + list(players)
        + [ps.player for ps in (list_stats.players if list_stats else [])]
    )
    unique_by_pk = {p.pk: p for p in all_player_instances}
    game_list_label_map = disambiguate_labels(list(unique_by_pk.values()))
    for p in all_player_instances:
        p._label_override = game_list_label_map.get(p.pk, p.display_label)

    stats_player_count = len(list_stats.players) if list_stats else 0
    list_density = resolve_game_list_density(
        table_player_count=len(player_columns),
        stats_player_count=stats_player_count,
    )

    groups = visible_groups(request.user, session=request.session).order_by("name")
    has_any_games = Game.objects.filter(group__in=groups).exists()
    summary_params = dict(params)
    summary_params["period_label"] = period_ctx.get("period_label", "")

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
                params=summary_params,
                groups=groups,
                players=players,
                locations=locations,
            ),
            "show_empty_filters_message": has_any_games,
            "groups": groups,
            "game_types": [
                (code, name)
                for code, name in game_type_choices()
                if code in available_game_type_codes(request)
            ],
            "game_type_locked": len(available_game_type_codes(request)) <= 1,
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
            "shutout_filter": (
                {
                    "label": shutout_config.label,
                    "checked": params.get("shutout") in ("1", "true", "on"),
                    "input_id": "filter-shutout-only",
                }
                if shutout_config is not None
                else None
            ),
            "shutout_icon_url": (
                shutout_icon_url(params["game_type"]) if shutout_config else ""
            ),
            "game_feature_filters": leaderboard_filter_rows(
                game_type_code=params["game_type"],
                selections=resolve_feature_selections(
                    params, game_type_code=params["game_type"]
                ),
                select_id_prefix="filter",
            ),
            **period_ctx,
        },
    )


@demo_or_login_required
def game_create(request: HttpRequest) -> HttpResponse:
    show_roster = False
    participant_error = None
    post_for_rows = None
    reused_participant_rows = None
    player_picker_start_collapsed = False
    preserve_setup_location = False
    game_type = None
    seeded_score_type: str | None = None

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
                    reused_participant_rows = []
                    reuse_game_id = (request.POST.get("reuse_game_id") or "").strip()
                    source_for_reuse = None
                    if reuse_game_id.isdigit():
                        source_for_reuse = Game.objects.filter(
                            pk=int(reuse_game_id),
                            group=group,
                            game_type_code=game_type_code,
                        ).first()
                        if source_for_reuse is not None:
                            reused_participant_rows = participant_rows_from_game(
                                source_for_reuse
                            )
                    if not reused_participant_rows:
                        reused_participant_rows = previous_game_participant_rows(
                            group, game_type_code
                        )
                    if not reused_participant_rows:
                        messages.info(
                            request,
                            "No previous game found for this group and game type.",
                        )
                        # Stay on unified screen with empty roster.
                        show_roster = True
                    else:
                        show_roster = True
                        player_picker_start_collapsed = True
                        if source_for_reuse is not None:
                            seeded_score_type = source_for_reuse.score_type or None
                else:
                    show_roster = True
                if show_roster:
                    persist_game_type_code(request, game_type_code)
                    persist_group_id(request, group.pk)
    else:
        initial = {}
        reuse_from_pk = (request.GET.get("reuse_from") or "").strip()
        pick_from_pk = (request.GET.get("pick_from") or "").strip()
        source_game = None
        if reuse_from_pk and request.user.is_authenticated:
            source_game = (
                Game.objects.filter(pk=reuse_from_pk)
                .select_related("group", "location")
                .prefetch_related(
                    "participant_results__player__linked_user",
                    "participant_results__player__team_members__member__linked_user",
                )
                .first()
            )
            if source_game is not None and can_edit_group(
                request.user, source_game.group
            ):
                reused_participant_rows = participant_rows_from_game(source_game)
                if reused_participant_rows:
                    show_roster = True
                    player_picker_start_collapsed = True
                    preserve_setup_location = True
                    seeded_score_type = source_game.score_type or None
                    initial["group"] = source_game.group_id
                    initial["game_type_code"] = source_game.game_type_code
                    initial["played_on"] = timezone.localdate()
                    if source_game.location_id:
                        initial["location_name"] = source_game.location.name
                    persist_game_type_code(request, source_game.game_type_code)
                    persist_group_id(request, source_game.group_id)
                else:
                    source_game = None
            else:
                source_game = None

        if source_game is None and pick_from_pk and request.user.is_authenticated:
            pick_game = (
                Game.objects.filter(pk=pick_from_pk)
                .select_related("group", "location")
                .first()
            )
            if pick_game is not None and can_edit_group(request.user, pick_game.group):
                # Same as reuse_from for group/type/date/location, but start with
                # an empty roster so the user picks players on the record screen.
                show_roster = True
                player_picker_start_collapsed = False
                preserve_setup_location = True
                seeded_score_type = pick_game.score_type or None
                reused_participant_rows = []
                initial["group"] = pick_game.group_id
                initial["game_type_code"] = pick_game.game_type_code
                initial["played_on"] = timezone.localdate()
                if pick_game.location_id:
                    initial["location_name"] = pick_game.location.name
                persist_game_type_code(request, pick_game.game_type_code)
                persist_group_id(request, pick_game.group_id)
                source_game = pick_game

        if source_game is None:
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
                available_codes=available_game_type_codes(request),
            )
        form = GameRecordForm(user=request.user, initial=initial)

    group = _resolve_group(request, form)
    if group is None and form.initial.get("group"):
        group = Group.objects.filter(pk=form.initial["group"]).first()
    if request.method == "POST" and group:
        action = request.POST.get("action")
        if action in ("load_roster", "reuse_roster", "save") and not can_edit_group(
            request.user, group
        ):
            raise Http404
    if show_roster and group and not can_edit_group(request.user, group):
        raise Http404

    if form.is_bound and form.is_valid() and form.cleaned_data.get("game_type_code"):
        game_type_code = form.cleaned_data["game_type_code"]
    else:
        game_type_code = (
            request.POST.get("game_type_code")
            or form.initial.get("game_type_code")
            or ""
        )
    game_type = get_game_type(game_type_code) if game_type_code else None

    # Unified Record Game: show players/scores whenever group + type resolve
    # and the user can record. Guests see context fields plus a login CTA.
    if (
        not show_roster
        and group is not None
        and game_type is not None
        and request.user.is_authenticated
        and can_edit_group(request.user, group)
    ):
        show_roster = True

    roster = []
    smart_suggestions = []
    participant_rows = []
    if group and show_roster and game_type is not None:
        if request.user.is_authenticated and can_edit_group(request.user, group):
            roster = roster_for_group(group, game_type_code=game_type_code)
            smart_suggestions = suggest_side_entries(group, game_type_code)
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
                "location_lat": request.POST.get("location_lat", ""),
                "location_lon": request.POST.get("location_lon", ""),
                "location_city": request.POST.get("location_city", ""),
                "location_state": request.POST.get("location_state", ""),
                "location_country": request.POST.get("location_country", ""),
                "location_postal_code": request.POST.get("location_postal_code", ""),
                "location_street_address": request.POST.get(
                    "location_street_address", ""
                ),
                "location_place_id": request.POST.get("location_place_id", ""),
                "location_geocode_source": request.POST.get(
                    "location_geocode_source", ""
                ),
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
                    geo=location_geo_from_form(save_form),
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
                    **record_game_kwargs_from_post(
                        save_form.cleaned_data["game_type_code"],
                        request.POST,
                    ),
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
                detail_url = reverse("games:detail", kwargs={"pk": game.pk})
                return redirect(f"{detail_url}?record_again=1")

    played_on_value = ""
    played_on_display = ""
    location_name = ""
    location_geo = location_geo_post_values(None)
    record_game_feature_values: dict = {}
    record_game_feature_field_rows: list = []
    selected_setup_game_type_code = ""
    if form.is_bound:
        selected_setup_game_type_code = (form.data.get("game_type_code") or "").strip()
    else:
        initial_code = form.initial.get("game_type_code")
        if initial_code:
            selected_setup_game_type_code = str(initial_code).strip()
    allowed_types = frozenset(available_game_type_codes(request))
    setup_game_type_options = [
        (code, name, game_type_icon_url(code))
        for code, name in game_type_choices()
        if code in allowed_types
    ]
    selected_setup_game_type_icon_url = (
        game_type_icon_url(selected_setup_game_type_code)
        if selected_setup_game_type_code in GAME_TYPES
        else ""
    )
    if group and game_type is not None:
        played_on_value, played_on_display = _played_on_value_and_display(form)
        if form.is_bound:
            location_name = form.data.get("location_name", "")
            location_geo = location_geo_post_values(form.data)
            record_game_feature_values = resolve_record_game_feature_values(
                game_type.code,
                post_data=request.POST,
                seeded_score_type=seeded_score_type,
                last_score_type=last_recorded_score_type(
                    request.user if request.user.is_authenticated else None,
                    game_type.code,
                ),
            )
        else:
            if form.initial.get("location_name"):
                location_name = form.initial.get("location_name", "")
                location_geo = location_geo_post_values(form.initial)
            else:
                location_name = form["location_name"].value() or ""
            record_game_feature_values = resolve_record_game_feature_values(
                game_type.code,
                seeded_score_type=seeded_score_type,
                last_score_type=last_recorded_score_type(
                    request.user if request.user.is_authenticated else None,
                    game_type.code,
                ),
            )
        record_game_feature_field_rows = record_game_feature_fields(
            game_type.code,
            values=record_game_feature_values,
        )

    locked = is_game_type_locked(request)
    heading_type = game_type
    if heading_type is None and locked:
        locked_code = preferred_game_type_code(request)
        if locked_code in GAME_TYPES:
            heading_type = get_game_type(locked_code)
    if locked and heading_type is not None:
        record_game_heading = f"{heading_type.name} - Record Game"
        record_game_heading_icon_url = game_type_icon_url(heading_type.code)
    else:
        record_game_heading = "Record Game"
        record_game_heading_icon_url = ""

    from leaderlodge.insights.views import insights_feature_enabled

    return render(
        request,
        "games/game_form.html",
        {
            "form": form,
            "group": group,
            "participant_rows": participant_rows,
            "roster": roster,
            "smart_suggestions": smart_suggestions,
            "game_rules_summary": (
                record_game_rules_summary(game_type.code) if game_type else ""
            ),
            "game_type": game_type,
            "record_game_feature_fields": record_game_feature_field_rows,
            "show_roster": show_roster and group is not None and game_type is not None,
            "participant_error": participant_error,
            "played_on_value": played_on_value,
            "played_on_display": played_on_display,
            "location_name": location_name,
            "location_geo": location_geo,
            "setup_game_type_options": setup_game_type_options,
            "selected_setup_game_type_code": selected_setup_game_type_code,
            "selected_setup_game_type_icon_url": selected_setup_game_type_icon_url,
            "default_participant_score": (
                default_participant_score_value(game_type.code) if game_type else ""
            ),
            "player_picker_start_collapsed": player_picker_start_collapsed,
            "preserve_setup_location": preserve_setup_location,
            "google_places_api_key": (
                getattr(settings, "GOOGLE_PLACES_API_KEY", "")
                if request.user.is_authenticated
                else ""
            ),
            "game_type_locked": locked,
            "record_game_heading": record_game_heading,
            "record_game_heading_icon_url": record_game_heading_icon_url,
            "insights_ready": insights_feature_enabled(),
            "ai_game_entry_mic_enabled": bool(
                SiteSettings.load().ai_game_entry_mic_enabled
            ),
            "ai_entry_example": (ai_entry_example(game_type.code) if game_type else ""),
            "ai_entry_help_content": (
                ai_entry_help_content(game_type.code) if game_type else ""
            ),
        },
    )


@login_required
@require_POST
def game_parse_recording(request: HttpRequest) -> JsonResponse:
    """Parse a voice/typed transcript into a Record Game draft (no save)."""
    from leaderlodge.games.voice_draft import parse_recording_transcript
    from leaderlodge.insights.model_selection import preferred_insight_model_id
    from leaderlodge.insights.providers.base import InsightProviderError
    from leaderlodge.insights.rate_limit import (
        InsightRateLimitExceeded,
        check_insight_rate_limit,
    )
    from leaderlodge.insights.views import insights_feature_enabled

    if not insights_feature_enabled():
        return JsonResponse(
            {"error": "AI features are not enabled."},
            status=503,
        )

    try:
        payload = json.loads(request.body.decode() or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse({"error": "Invalid JSON body."}, status=400)

    group_id = str(payload.get("group") or "").strip()
    transcript = str(payload.get("transcript") or "").strip()
    default_type = str(payload.get("game_type_code") or "").strip()
    if not group_id.isdigit():
        return JsonResponse({"error": "Group is required."}, status=400)
    if not transcript:
        return JsonResponse({"error": "Transcript is required."}, status=400)

    group = Group.objects.filter(pk=int(group_id)).first()
    if group is None:
        return JsonResponse({"error": "Group not found."}, status=404)
    if not can_edit_group(request.user, group):
        return JsonResponse(
            {"error": "You cannot record games in this group."},
            status=403,
        )

    model_slug = preferred_insight_model_id(request)
    try:
        check_insight_rate_limit(request, user=request.user, model_slug=model_slug)
    except InsightRateLimitExceeded as exc:
        return JsonResponse({"error": str(exc)}, status=429)

    try:
        draft = parse_recording_transcript(
            group=group,
            transcript=transcript,
            user=request.user,
            model_slug=model_slug,
            default_game_type_code=default_type,
        )
    except InsightProviderError as exc:
        return JsonResponse({"error": str(exc)}, status=502)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except Exception:
        return JsonResponse(
            {"error": "Could not parse that entry. Try again."},
            status=500,
        )

    return JsonResponse({"draft": draft})


@login_required
def game_suggest_sides(request: HttpRequest) -> JsonResponse:
    group_id = request.GET.get("group", "").strip()
    game_type_code = (
        _requested_game_type_code(request)
        or (request.GET.get("game_type_code") or "").strip()
    )
    if not group_id.isdigit() or game_type_code not in GAME_TYPES:
        return JsonResponse({"suggestions": []})

    group = Group.objects.filter(pk=int(group_id)).first()
    if group is None or not can_edit_group(request.user, group):
        raise Http404

    exclude_raw = (request.GET.get("exclude") or "").strip()
    exclude_ids = {
        int(part) for part in exclude_raw.split(",") if part.strip().isdigit()
    }

    if (request.GET.get("lineup") or "").strip() == "1":
        suggestions = suggest_lineup_entries(group, game_type_code)
        return JsonResponse({"suggestions": suggestions})

    query = (request.GET.get("q") or "").strip()
    teammate_mode = (request.GET.get("mode") or "").strip() == "teammate"

    suggestions = suggest_side_entries(
        group,
        game_type_code,
        exclude_player_ids=exclude_ids,
        query=query,
        teammate_mode=teammate_mode,
    )
    return JsonResponse({"suggestions": suggestions})


@login_required
def game_reuse_preview(request: HttpRequest) -> JsonResponse:
    group_id = request.GET.get("group", "").strip()
    game_type_code = (
        _requested_game_type_code(request)
        or (request.GET.get("game_type_code") or "").strip()
    )
    if not group_id.isdigit() or game_type_code not in GAME_TYPES:
        return JsonResponse(
            {
                "available": False,
                "summary": "",
                "labels": [],
                "options": [],
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
    if not can_view_group(request.user, game.group, session=request.session):
        raise Http404

    matchup = build_matchup_view(game)
    apply_label_overrides([col.player for col in matchup.players])
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
        ).prefetch_related(
            "participant_results__player__linked_user__profile",
        ),
        pk=pk,
    )
    if not can_view_group(request.user, game.group, session=request.session):
        raise Http404

    game_type = get_game_type(game.game_type_code)
    results = list(game.participant_results.order_by("placement", "pk"))
    apply_label_overrides([r.player for r in results])
    can_invite_guests = can_manage_group_members(request.user, game.group)
    can_set_place = can_assign_location_place(request.user, game.group) and (
        game.location is not None
    )
    location_is_geocoded = bool(
        game.location
        and game.location.lat is not None
        and game.location.lon is not None
    )
    google_places_api_key = getattr(settings, "GOOGLE_PLACES_API_KEY", "")
    can_show_place = (
        (not can_set_place) and location_is_geocoded and bool(google_places_api_key)
    )
    location_game_count = 0
    if game.location_id:
        from leaderlodge.games.models import Game as GameModel

        location_game_count = GameModel.objects.filter(
            location_id=game.location_id
        ).count()
    show_record_again = (
        can_edit_group(request.user, game.group)
        and request.GET.get("record_again") == "1"
    )
    record_again_reuse_options = []
    if show_record_again:
        record_again_reuse_options = reuse_players_summary(
            game.group, game.game_type_code
        ).get("options", [])
    from leaderlodge.games.shutouts import (
        is_double_skunk_game,
        is_shutout_game,
        shutout_winner_result,
    )

    is_shutout = is_shutout_game(game.game_type_code, results)
    is_double_skunk = is_double_skunk_game(game.game_type_code, results)
    shutout_winner = shutout_winner_result(game.game_type_code, results)
    shutout_winner_player_id = (
        shutout_winner.player_id if shutout_winner is not None else None
    )
    result_rows = [
        {
            "result": r,
            "is_guest": r.player.linked_user is None,
            "email_verified": (
                is_email_verified(r.player.linked_user)
                if r.player.linked_user is not None
                else False
            ),
            "is_shutout_winner": (
                is_shutout
                and shutout_winner_player_id is not None
                and r.player_id == shutout_winner_player_id
            ),
            "is_double_skunk": (
                is_double_skunk
                and shutout_winner_player_id is not None
                and r.player_id == shutout_winner_player_id
            ),
        }
        for r in results
    ]

    return render(
        request,
        "games/game_detail.html",
        {
            "game": game,
            "game_type": game_type,
            "game_type_icon_url": game_type_icon_url(game.game_type_code),
            "shutout_icon_url": shutout_icon_url(game.game_type_code),
            "result_rows": result_rows,
            "score_type_label": (
                score_type_label(game.game_type_code, game.score_type)
                if game_type_has_score_type(game.game_type_code)
                else ""
            ),
            "score_type_field_label": game_type.score_type_field_label,
            "score_type_icon_url": score_type_icon_url(
                game.game_type_code, game.score_type
            ),
            "is_double": game.double_weight == 2,
            "is_half": game.half_weight == 2,
            "is_shutout": is_shutout,
            "is_double_skunk": is_double_skunk,
            "insights_enabled": insights_ui_enabled(),
            "insight_models": tuple(MODEL_REGISTRY.values()),
            "selected_insight_model": preferred_insight_model_id(request),
            "can_edit_game": user_can_edit_game(request.user, game),
            "can_invite_guests": can_invite_guests,
            "can_set_place": can_set_place,
            "can_show_place": can_show_place,
            "location_is_geocoded": location_is_geocoded,
            "location_game_count": location_game_count,
            "google_places_api_key": google_places_api_key,
            "show_record_again": show_record_again,
            "record_again_reuse_options": record_again_reuse_options,
        },
    )


@login_required
def game_edit_game(request: HttpRequest, pk: int) -> HttpResponse:
    game = get_object_or_404(
        Game.objects.select_related("group", "location").prefetch_related(
            "participant_results__player"
        ),
        pk=pk,
    )
    if not can_view_group(
        request.user, game.group, session=request.session
    ) or not user_can_edit_game(request.user, game):
        raise Http404

    game_type = get_game_type(game.game_type_code)
    results = list(
        game.participant_results.select_related("player").order_by("placement", "pk")
    )
    participant_error = None
    lineup_rows = None

    if request.method == "POST":
        form = GameEditForm(request.POST, game=game)
        if request.POST.getlist("participant_player_id"):
            try:
                parsed = parse_participants_from_post(request.POST, group=game.group)
                prepare_participant_rows(
                    parsed,
                    game.game_type_code,
                    no_score_tie=no_score_tie_requested(request.POST),
                )
                lineup_rows = parsed
            except ValidationError as exc:
                participant_error = str(exc)
        if form.is_valid() and participant_error is None:
            try:
                pre_resolve_location_geo = None
                if game.location_id:
                    pre_resolve_location_geo = (
                        game.location.lat,
                        game.location.lon,
                    )
                edit_kwargs = {
                    "game": game,
                    "user": request.user,
                    "notes": form.cleaned_data["notes"],
                    "score_updates": form.score_updates(),
                    "participant_removals": form.participant_removals(),
                    "lineup_rows": lineup_rows,
                    "new_location": form.resolved_location(),
                    "new_played_on": form.cleaned_data["played_on"],
                    "pre_resolve_location_geo": pre_resolve_location_geo,
                }
                if form.has_score_type_field():
                    edit_kwargs["new_score_type"] = form.cleaned_score_type()
                if form.has_half_game_field():
                    edit_kwargs["new_half_weight"] = form.cleaned_half_weight()
                summary = apply_game_edits(**edit_kwargs)
            except ValidationError as exc:
                messages.error(request, str(exc))
            else:
                if summary.logs:
                    messages.success(request, "Game updated.")
                    return redirect("games:detail", pk=game.pk)
                messages.warning(request, "No changes were made.")
    else:
        form = GameEditForm(game=game)

    if request.method == "POST" and request.POST.getlist("participant_player_id"):
        participant_rows = _participant_rows_from_post(game.group, request.POST)
    else:
        participant_rows = participant_rows_for_edit_game(game)

    roster = roster_for_group(game.group, game_type_code=game.game_type_code)
    smart_suggestions = suggest_side_entries(game.group, game.game_type_code)

    google_places_api_key = getattr(settings, "GOOGLE_PLACES_API_KEY", "")
    can_set_place = can_assign_location_place(request.user, game.group) and (
        game.location_id is not None
    )
    can_use_location_map = bool(google_places_api_key)
    location_is_geocoded = bool(
        game.location_id
        and game.location.lat is not None
        and game.location.lon is not None
    )
    location_game_count = 0
    if game.location_id:
        from leaderlodge.games.models import Game as GameModel

        location_game_count = GameModel.objects.filter(
            location_id=game.location_id
        ).count()

    return render(
        request,
        "games/game_edit.html",
        {
            "game": game,
            "game_type": game_type,
            "game_type_icon_url": game_type_icon_url(game.game_type_code),
            "form": form,
            "results": results,
            "participant_rows": participant_rows,
            "participant_error": participant_error,
            "roster": roster,
            "smart_suggestions": smart_suggestions,
            "default_participant_score": default_participant_score_value(
                game.game_type_code
            ),
            "is_no_score_tie": (
                no_score_tie_requested(request.POST)
                if request.method == "POST"
                else lineup_is_no_score_tie(participant_rows, game.game_type_code)
            ),
            "score_type_choice_options": [
                {
                    "value": value,
                    "label": label,
                    "icon_url": score_type_icon_url(game.game_type_code, value),
                }
                for value, label in score_type_choices_for(game.game_type_code)
            ],
            "score_type_icon_url": score_type_icon_url(
                game.game_type_code, game.score_type
            ),
            "is_double": game.double_weight == 2,
            "is_half": game.half_weight == 2,
            "google_places_api_key": google_places_api_key,
            "can_set_place": can_set_place,
            "can_use_location_map": can_use_location_map,
            "location_is_geocoded": location_is_geocoded,
            "location_game_count": location_game_count,
        },
    )


@login_required
@require_POST
def game_delete(request: HttpRequest, pk: int) -> HttpResponse:
    """Delete a game. Same permission gate as Edit Game (recorder or staff)."""
    game = get_object_or_404(
        Game.objects.select_related("group").prefetch_related(
            "participant_results__player"
        ),
        pk=pk,
    )
    if not can_view_group(
        request.user, game.group, session=request.session
    ) or not user_can_edit_game(request.user, game):
        raise Http404

    group_id = game.group_id
    game_type_code = game.game_type_code
    game_type_name = get_game_type(game_type_code).name
    played_on = game.played_on
    delete_game(game=game, user=request.user)
    played_label = played_on.strftime("%b %d, %Y").replace(" 0", " ")
    messages.success(
        request,
        f"Deleted {game_type_name} game from {played_label}.",
    )
    list_url = reverse("games:list")
    query = urlencode({"group": group_id, "game_type_code": game_type_code})
    return redirect(f"{list_url}?{query}")
