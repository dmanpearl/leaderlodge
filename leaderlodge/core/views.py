from dataclasses import dataclass

from django.contrib.auth.views import redirect_to_login
from django.db.models import QuerySet
from django.http import HttpResponse
from django.shortcuts import render
from django.urls import reverse

from leaderlodge.core.decorators import demo_or_login_required
from leaderlodge.games.display import winner_labels_for_games
from leaderlodge.groups.names import apply_label_overrides
from leaderlodge.games.game_type_icons import game_type_icon_image
from leaderlodge.games.models import Game
from leaderlodge.games.registry import get_game_type
from leaderlodge.groups.models import Group
from leaderlodge.groups.services import (
    editable_groups,
    get_demo_group,
    resolve_user_group,
    user_groups,
)
from leaderlodge.leaderboards.service import PlayerRanking, get_player_rankings


@dataclass(frozen=True)
class DashboardRecentGame:
    game: Game
    winner_label: str


@dataclass(frozen=True)
class DashboardLeaderboardRow:
    rank: int
    player_label: str
    rank_score: float
    group_name: str | None = None
    group_id: int | None = None


@dataclass(frozen=True)
class DashboardLeaderboardCard:
    game_type_code: str
    game_type_name: str
    rows: list[DashboardLeaderboardRow]
    composite: bool
    leaderboard_url: str
    group_id: int | None = None
    icon_class: str = ""
    icon_image: str = ""


def _dashboard_leaderboard_icons(game_type_code: str) -> tuple[str, str]:
    icon_image = game_type_icon_image(game_type_code)
    if icon_image:
        return "", icon_image
    return "", ""


def _game_type_codes_for_groups(groups: QuerySet[Group] | list[Group]) -> list[str]:
    return list(
        Game.objects.filter(group__in=groups)
        .values_list("game_type_code", flat=True)
        .distinct()
        .order_by("game_type_code")
    )


def _dashboard_ranking_sort_key(ranking: PlayerRanking) -> tuple:
    return (
        -ranking.rank_score,
        -ranking.games_played,
        -ranking.finish_points,
        ranking.player.display_label.lower(),
        ranking.player.group.name.lower(),
    )


def _build_leaderboard_cards(
    request,
    groups: QuerySet[Group],
) -> list[DashboardLeaderboardCard]:
    from leaderlodge.accounts.game_selection import available_game_type_codes

    group_list = list(groups)
    if not group_list:
        return []

    composite = len(group_list) > 1
    cards: list[DashboardLeaderboardCard] = []
    allowed = frozenset(available_game_type_codes(request))

    for code in _game_type_codes_for_groups(group_list):
        if code not in allowed:
            continue
        game_type = get_game_type(code)
        combined: list[PlayerRanking] = []
        for group in group_list:
            combined.extend(get_player_rankings(group, game_type_code=code))

        if not combined:
            continue

        combined.sort(key=_dashboard_ranking_sort_key)
        apply_label_overrides([r.player for r in combined])
        top = combined[:5]

        if composite:
            rows = [
                DashboardLeaderboardRow(
                    rank=index,
                    player_label=row.player.display_label,
                    rank_score=row.rank_score,
                    group_name=row.player.group.name,
                    group_id=row.player.group_id,
                )
                for index, row in enumerate(top, start=1)
            ]
            leaderboard_url = f"{reverse('leaderboards:index')}?type={code}"
        else:
            group = group_list[0]
            rows = [
                DashboardLeaderboardRow(
                    rank=row.rank or index,
                    player_label=row.player.display_label,
                    rank_score=row.rank_score,
                    group_id=group.pk,
                )
                for index, row in enumerate(top, start=1)
            ]
            leaderboard_url = (
                f"{reverse('leaderboards:index')}" f"?group={group.pk}&type={code}"
            )

        icon_class, icon_image = _dashboard_leaderboard_icons(code)
        cards.append(
            DashboardLeaderboardCard(
                game_type_code=code,
                game_type_name=game_type.name,
                rows=rows,
                composite=composite,
                leaderboard_url=leaderboard_url,
                # None when composite: rows span multiple groups, so there is
                # no single group to preselect for the record-game shortcut.
                group_id=None if composite else group_list[0].pk,
                icon_class=icon_class,
                icon_image=icon_image,
            )
        )

    return cards


def _render_dashboard(
    request,
    *,
    groups: QuerySet[Group],
    is_demo_landing: bool,
    can_record_games: bool,
):
    default_group = (
        resolve_user_group(request.user, None)
        if request.user.is_authenticated
        else None
    )
    if default_group is None and groups.count() == 1:
        default_group = groups.first()

    from leaderlodge.accounts.game_selection import (
        available_game_type_codes,
        is_game_type_locked,
        preferred_game_type_code,
    )

    allowed_types = available_game_type_codes(request)
    recent_games_qs = Game.objects.filter(group__in=groups).select_related(
        "group", "location"
    )
    if len(allowed_types) == 1:
        recent_games_qs = recent_games_qs.filter(game_type_code=allowed_types[0])
    recent_games_qs = list(recent_games_qs.order_by("-played_on", "-created_at")[:5])
    winner_labels = winner_labels_for_games(recent_games_qs)
    recent_games = [
        DashboardRecentGame(
            game=game,
            winner_label=winner_labels.get(game.pk, "-"),
        )
        for game in recent_games_qs
    ]

    leaderboard_cards = _build_leaderboard_cards(request, groups)
    composite_leaderboards = groups.count() > 1
    record_game_url_group = (
        default_group.pk if default_group and can_record_games else None
    )
    from leaderlodge.games.game_type_icons import game_type_icon_url

    locked = is_game_type_locked(request)
    locked_type_name = ""
    locked_type_code = ""
    if locked:
        locked_type_code = preferred_game_type_code(request)
        if locked_type_code:
            locked_type_name = get_game_type(locked_type_code).name
    if is_demo_landing:
        dashboard_heading = "Demo"
    elif locked and locked_type_name:
        dashboard_heading = locked_type_name
    else:
        dashboard_heading = "Dashboard"
    dashboard_heading_icon_url = (
        game_type_icon_url(locked_type_code) if locked and locked_type_code else ""
    )

    return render(
        request,
        "core/dashboard.html",
        {
            "recent_games": recent_games,
            "leaderboard_cards": leaderboard_cards,
            "composite_leaderboards": composite_leaderboards,
            "has_groups": groups.exists(),
            "record_game_url_group": record_game_url_group,
            "is_demo_landing": is_demo_landing,
            "can_record_games": can_record_games,
            "dashboard_heading": dashboard_heading,
            "dashboard_heading_icon_url": dashboard_heading_icon_url,
            "game_type_locked": locked,
            # Collapse chrome only when multiple game-type cards are shown.
            "dashboard_sections_collapsible": len(leaderboard_cards) > 1,
        },
    )


@demo_or_login_required
def dashboard(request):
    if request.user.is_authenticated:
        groups = user_groups(request.user).order_by("name")
        return _render_dashboard(
            request,
            groups=groups,
            is_demo_landing=False,
            can_record_games=editable_groups(request.user).exists(),
        )

    demo = get_demo_group()
    if demo is None:
        return redirect_to_login(request.get_full_path())

    return _render_dashboard(
        request,
        groups=Group.objects.filter(pk=demo.pk),
        is_demo_landing=True,
        can_record_games=False,
    )


def about(request):
    from leaderlodge.accounts.game_selection import is_game_type_locked
    from leaderlodge.games.game_type_icons import game_type_icon_url
    from leaderlodge.games.registry import GAME_TYPES

    game_types = [
        {
            "code": gt.code,
            "name": gt.name,
            "abbr": gt.abbr,
            "icon_url": game_type_icon_url(gt.code),
        }
        for gt in GAME_TYPES.values()
    ]
    return render(
        request,
        "core/about.html",
        {
            "about_game_types": game_types,
            "game_type_locked": is_game_type_locked(request),
        },
    )


def about_insights(request):
    return render(request, "core/about_insights.html")


def about_scoring(request):
    from leaderlodge.core.docs import rank_scoring_explainer_html

    return render(
        request,
        "core/about_scoring.html",
        {"scoring_doc_html": rank_scoring_explainer_html()},
    )


def robots_txt(request):
    lines = [
        "User-agent: *",
        "Allow: /",
        "Disallow: /admin/",
        "Disallow: /accounts/",
        "Disallow: /groups/",
        "Disallow: /games/",
        "Disallow: /leaderboards/",
        "Disallow: /insights/",
        "Disallow: /feedback/",
        "",
        "Sitemap: https://leaderlodge.com/sitemap.xml",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")
