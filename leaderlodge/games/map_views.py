"""Games map viewer page and GeoJSON API."""

from __future__ import annotations

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from leaderlodge.accounts.group_selection import resolve_group_id
from leaderlodge.accounts.game_selection import (
    available_game_type_codes,
    is_game_type_locked,
    preferred_game_type_code,
    requested_game_type_token,
)
from leaderlodge.core.decorators import demo_or_login_required
from leaderlodge.games.map_data import (
    build_map_features,
    expand_map_bbox,
    group_location_counts,
    map_city_choices,
    map_country_choices,
    map_geo_cascade_tree,
    map_geojson_collection,
    map_location_name_choices,
    map_state_choices,
    parse_map_bbox,
    resolve_map_group,
)
from leaderlodge.games.game_type_icons import game_type_icon_url
from leaderlodge.games.models import Game, GameParticipantResult
from leaderlodge.games.registry import GAME_TYPES, get_game_type
from leaderlodge.groups.models import GroupPlayer
from leaderlodge.groups.services import can_manage_group_members, visible_groups


def _map_params(request: HttpRequest) -> dict[str, str]:
    return {
        "group": (request.GET.get("group") or "").strip(),
        "game_type": requested_game_type_token(request),
        "player": (request.GET.get("player") or "").strip(),
        "city": (request.GET.get("city") or "").strip(),
        "state": (request.GET.get("state") or "").strip(),
        "country": (request.GET.get("country") or "").strip().upper(),
        "location_name": (request.GET.get("location_name") or "").strip(),
        "year": (request.GET.get("year") or "").strip(),
        "month": (request.GET.get("month") or "").strip(),
        "period_preset": (request.GET.get("period_preset") or "").strip(),
        "start_date": (request.GET.get("start_date") or "").strip(),
        "end_date": (request.GET.get("end_date") or "").strip(),
    }


def _resolve_map_params(request: HttpRequest, params: dict[str, str], groups) -> dict:
    resolved = dict(params)
    resolved["group"] = resolve_group_id(
        request,
        requested=params["group"],
        available_groups=groups,
        session=request.session,
    )
    if is_game_type_locked(request):
        resolved["game_type"] = preferred_game_type_code(request)
        return resolved
    game_type = params["game_type"]
    if game_type and game_type not in GAME_TYPES:
        game_type = ""
    # Empty means "all games" when unlocked.
    resolved["game_type"] = game_type
    return resolved


def _map_period_context(group, game_type_code: str, params: dict[str, str]):
    from leaderlodge.leaderboards.period import (
        PERIOD_PRESET_CHOICES,
        LeaderboardPeriod,
        period_filter_context,
    )

    if group is None:
        empty = LeaderboardPeriod.all_time()
        return empty, {
            "selected_period": empty,
            "period_year_options": [],
            "period_month_options": [],
            "period_preset_choices": PERIOD_PRESET_CHOICES,
            "period_show_custom_dates": params.get("period_preset") == "custom",
            "period_label": "",
        }

    # Period helpers expect a game type; use first played type when "all".
    code = game_type_code if game_type_code in GAME_TYPES else ""
    if not code:
        code = (
            Game.objects.filter(group=group)
            .order_by("game_type_code")
            .values_list("game_type_code", flat=True)
            .first()
            or ""
        )
    if not code:
        empty = LeaderboardPeriod.all_time()
        return empty, {
            "selected_period": empty,
            "period_year_options": [],
            "period_month_options": [],
            "period_preset_choices": PERIOD_PRESET_CHOICES,
            "period_show_custom_dates": params.get("period_preset") == "custom",
            "period_label": "",
        }

    period_ctx = period_filter_context(
        group=group,
        game_type_code=code,
        raw_year=params.get("year", ""),
        raw_month=params.get("month", ""),
        raw_preset=params.get("period_preset", ""),
        raw_start_date=params.get("start_date", ""),
        raw_end_date=params.get("end_date", ""),
    )
    return period_ctx["selected_period"], period_ctx


def _player_choices_for_map(group, game_type_code: str):
    games_qs = Game.objects.filter(group=group)
    if game_type_code in GAME_TYPES:
        games_qs = games_qs.filter(game_type_code=game_type_code)
    player_ids = (
        GameParticipantResult.objects.filter(game__in=games_qs)
        .values_list("player_id", flat=True)
        .distinct()
    )
    return (
        GroupPlayer.objects.filter(pk__in=player_ids, group=group)
        .select_related("linked_user")
        .order_by("display_name", "pk")
    )


def _game_type_options_for_map(request: HttpRequest, group) -> list[tuple[str, str]]:
    codes = set(
        Game.objects.filter(group=group)
        .values_list("game_type_code", flat=True)
        .distinct()
    )
    options = []
    for code in available_game_type_codes(request):
        if code in codes and code in GAME_TYPES:
            options.append((code, GAME_TYPES[code].name))
    return options


def _map_filter_query(params: dict[str, str]) -> str:
    from urllib.parse import urlencode

    query = {}
    for k, v in params.items():
        if not v:
            continue
        if k == "game_type":
            query["type"] = v
        else:
            query[k] = v
    return urlencode(query)


@demo_or_login_required
def game_map(request: HttpRequest) -> HttpResponse:
    groups = list(
        visible_groups(request.user, session=request.session).order_by("name")
    )
    raw = _map_params(request)
    params = _resolve_map_params(request, raw, groups)

    selected_group = resolve_map_group(
        user=request.user,
        group_id=params["group"],
        groups=groups,
    )
    if selected_group is not None:
        params["group"] = str(selected_group.pk)

    # Canonicalize bookmarkable URL when group was inferred.
    if groups and params["group"] and raw["group"] != params["group"]:
        query = _map_filter_query(params)
        url = reverse("games:map")
        return redirect(f"{url}?{query}" if query else url)

    selected_period, period_ctx = _map_period_context(
        selected_group,
        params["game_type"],
        params,
    )
    params.update(
        {
            "year": "",
            "month": "",
            "period_preset": "",
            "start_date": "",
            "end_date": "",
        }
    )
    params.update(selected_period.query_params())
    if raw.get("period_preset") == "custom" and not selected_period.is_filtered:
        params["period_preset"] = "custom"

    features: list = []
    geocoded_count = 0
    location_count = 0
    country_choices: list[str] = []
    state_choices: list[str] = []
    city_choices: list[str] = []
    location_name_choices: list[str] = []
    geo_cascade_tree: dict = {}
    players = []
    game_type_options: list[tuple[str, str]] = []
    can_manage_locations = False

    if selected_group is not None:
        location_count, geocoded_count = group_location_counts(selected_group)
        country_choices = map_country_choices(selected_group)
        state_choices = map_state_choices(
            selected_group, country=params.get("country", "")
        )
        city_choices = map_city_choices(
            selected_group,
            country=params.get("country", ""),
            state=params.get("state", ""),
        )
        location_name_choices = map_location_name_choices(selected_group)
        geo_cascade_tree = map_geo_cascade_tree(selected_group)
        players = list(_player_choices_for_map(selected_group, params["game_type"]))
        game_type_options = _game_type_options_for_map(request, selected_group)
        can_manage_locations = can_manage_group_members(request.user, selected_group)
        if params.get("player") and not any(
            str(p.pk) == params["player"] for p in players
        ):
            params["player"] = ""
        if params.get("country") and params["country"].upper() not in {
            c.upper() for c in country_choices
        }:
            params["country"] = ""
        if params.get("state") and params["state"] not in state_choices:
            params["state"] = ""
            city_choices = map_city_choices(
                selected_group,
                country=params.get("country", ""),
                state="",
            )
        features = build_map_features(
            group=selected_group,
            game_type_code=params["game_type"],
            player_id=params["player"],
            period=selected_period,
            city=params["city"],
            state=params["state"],
            country=params["country"],
            location_name=params["location_name"],
        )

    api_query = _map_filter_query(params)
    games_list_base = reverse("games:list")
    location_detail_url_template = ""
    if selected_group is not None:
        location_detail_url_template = reverse(
            "groups:location_detail",
            kwargs={"pk": selected_group.pk, "loc_pk": 999999999},
        ).replace("999999999", "__LOC__")
    empty_no_pins = (
        selected_group is not None and location_count > 0 and geocoded_count == 0
    )

    locked = is_game_type_locked(request)
    map_heading = "Map"
    map_heading_icon_url = ""
    if locked:
        locked_code = preferred_game_type_code(request)
        if locked_code in GAME_TYPES:
            map_heading = get_game_type(locked_code).name
            map_heading_icon_url = game_type_icon_url(locked_code)

    return render(
        request,
        "games/game_map.html",
        {
            "groups": groups,
            "selected_group": selected_group,
            "params": params,
            "game_type_options": game_type_options,
            "game_type_locked": locked,
            "map_heading": map_heading,
            "map_heading_icon_url": map_heading_icon_url,
            "players": players,
            "country_choices": country_choices,
            "state_choices": state_choices,
            "city_choices": city_choices,
            "location_name_choices": location_name_choices,
            "geo_cascade_tree": geo_cascade_tree,
            "features": features,
            "feature_count": len(features),
            "geocoded_count": geocoded_count,
            "location_count": location_count,
            "empty_no_pins": empty_no_pins,
            "can_manage_locations": can_manage_locations,
            "map_api_query": api_query,
            "games_list_url": games_list_base,
            "location_detail_url_template": location_detail_url_template,
            "google_places_api_key": getattr(settings, "GOOGLE_PLACES_API_KEY", ""),
            **period_ctx,
        },
    )


@demo_or_login_required
def map_locations_api(request: HttpRequest) -> JsonResponse:
    groups = list(
        visible_groups(request.user, session=request.session).order_by("name")
    )
    raw = _map_params(request)
    params = _resolve_map_params(request, raw, groups)
    selected_group = resolve_map_group(
        user=request.user,
        group_id=params["group"],
        groups=groups,
    )
    if selected_group is None:
        return JsonResponse(map_geojson_collection([]))

    selected_period, _period_ctx = _map_period_context(
        selected_group,
        params["game_type"],
        params,
    )
    bbox = parse_map_bbox(request.GET.get("bbox", ""))
    if bbox is not None:
        bbox = expand_map_bbox(bbox)
    features = build_map_features(
        group=selected_group,
        game_type_code=params["game_type"],
        player_id=params["player"],
        period=selected_period,
        city=params["city"],
        state=params["state"],
        country=params["country"],
        location_name=params["location_name"],
        bbox=bbox,
    )
    return JsonResponse(map_geojson_collection(features))
