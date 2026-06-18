from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.dateparse import parse_date

from leaderlodge.games.forms import (
    GameRecordForm,
    parse_participants_from_post,
    prepare_participant_rows,
)
from leaderlodge.games.list_stats import build_game_list_stats
from leaderlodge.games.list_table import build_game_list_table
from leaderlodge.games.models import Game
from leaderlodge.games.registry import GAME_TYPES, game_type_choices, get_game_type
from leaderlodge.games.services import ParticipantInput, record_game
from leaderlodge.groups.models import Group, Location
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
        "location": request.GET.get("location", "").strip(),
        "sort": sort,
    }


def _filtered_games_queryset(user, params: dict[str, str]):
    games_qs = Game.objects.filter(group__in=user_groups(user)).select_related(
        "group", "recorded_by", "location"
    )

    if params["group"].isdigit():
        games_qs = games_qs.filter(group_id=int(params["group"]))
    if params["game_type"] in GAME_TYPES:
        games_qs = games_qs.filter(game_type_code=params["game_type"])
    if params["location"].isdigit():
        games_qs = games_qs.filter(location_id=int(params["location"]))

    if params["sort"] == "asc":
        return games_qs.order_by("played_on", "created_at")
    return games_qs.order_by("-played_on", "-created_at")


def _location_choices_for_game_list(user, params: dict[str, str]):
    games_qs = Game.objects.filter(
        group__in=user_groups(user),
        location__isnull=False,
    )
    if params["group"].isdigit():
        games_qs = games_qs.filter(group_id=int(params["group"]))
    if params["game_type"] in GAME_TYPES:
        games_qs = games_qs.filter(game_type_code=params["game_type"])

    location_ids = games_qs.values_list("location_id", flat=True).distinct()
    return Location.objects.filter(pk__in=location_ids).order_by("name")


def _sanitize_game_list_params(
    params: dict[str, str],
    locations,
) -> dict[str, str]:
    sanitized = dict(params)
    if sanitized["location"].isdigit():
        valid_ids = {location.pk for location in locations}
        if int(sanitized["location"]) not in valid_ids:
            sanitized["location"] = ""
    return sanitized


def _game_list_filter_query(params: dict[str, str]) -> str:
    from urllib.parse import urlencode

    return urlencode({key: value for key, value in params.items() if value})


def _game_list_has_filters(params: dict[str, str]) -> bool:
    return any(params[key] for key in ("group", "game_type", "location"))


def _player_rows(players, post=None):
    rows = []
    for player in players:
        if post is not None:
            rows.append(
                {
                    "player": player,
                    "played": post.get(f"play_{player.pk}") == "on",
                    "score": post.get(f"score_{player.pk}", "0"),
                }
            )
        else:
            rows.append(
                {
                    "player": player,
                    "played": False,
                    "score": "",
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
    locations = _location_choices_for_game_list(request.user, params)
    params = _sanitize_game_list_params(params, locations)
    games_qs = _filtered_games_queryset(request.user, params)
    list_stats = build_game_list_stats(
        games_qs=games_qs,
        game_type_code=params["game_type"],
    )
    paginator = Paginator(games_qs, GAMES_PER_PAGE)
    page = paginator.get_page(request.GET.get("page"))
    games = list(page.object_list)
    player_columns, game_rows = build_game_list_table(games)

    groups = user_groups(request.user).order_by("name")

    return render(
        request,
        "games/game_list.html",
        {
            "page": page,
            "game_rows": game_rows,
            "player_columns": player_columns,
            "list_stats": list_stats,
            "params": params,
            "filter_query": _game_list_filter_query(params),
            "has_filters": _game_list_has_filters(params),
            "groups": groups,
            "game_types": game_type_choices(),
            "locations": locations,
            "show_group_column": not params["group"],
            "show_game_type_column": not params["game_type"],
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

    players = []
    if group and show_roster:
        players = list(group.players.filter(is_active=True).order_by("display_name"))

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
            rows = parse_participants_from_post(request.POST, players)
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
            "player_rows": _player_rows(players, post_for_rows),
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
