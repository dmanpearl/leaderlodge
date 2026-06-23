from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from leaderlodge.accounts.game_selection import resolve_game_type_code
from leaderlodge.core.decorators import demo_or_login_required
from leaderlodge.games.registry import get_game_type
from leaderlodge.groups.forms import GroupForm, GroupMemberForm, GroupPlayerForm
from leaderlodge.groups.models import Group
from leaderlodge.groups.locations import locations_for_group
from leaderlodge.groups.player_search import search_group_players
from leaderlodge.groups.services import (
    add_guest_player,
    add_group_member,
    can_view_group,
    create_group_with_owner,
    user_is_member,
    visible_groups,
)
from leaderlodge.leaderboards.ranking import SORTABLE_COLUMNS
from leaderlodge.leaderboards.service import get_group_roster_standings


def _game_type_codes_for_group(group: Group) -> list[str]:
    from leaderlodge.games.models import Game

    return list(
        Game.objects.filter(group=group)
        .values_list("game_type_code", flat=True)
        .distinct()
        .order_by("game_type_code")
    )


def _group_detail_context(group: Group, request: HttpRequest) -> dict:
    memberships = group.memberships.select_related("user").order_by("user__username")
    game_type_codes = _game_type_codes_for_group(group)
    if game_type_codes:
        selected_game_type_code = resolve_game_type_code(
            request,
            requested=request.GET.get("game_type_code", "").strip(),
            available_codes=game_type_codes,
        )
    else:
        selected_game_type_code = None

    sort = request.GET.get("sort", "rank")
    if sort not in SORTABLE_COLUMNS:
        sort = "rank"
    ascending = request.GET.get("dir", "asc") != "desc"

    standings = []
    selected_game_type = None
    show_losses = False
    if selected_game_type_code:
        selected_game_type = get_game_type(selected_game_type_code)
        show_losses = selected_game_type.supports_loser
        standings = get_group_roster_standings(
            group,
            game_type_code=selected_game_type_code,
            sort=sort,
            ascending=ascending,
        )

    game_type_options = [
        (code, get_game_type(code).name) for code in game_type_codes
    ]

    return {
        "group": group,
        "member_rows": memberships,
        "member_form": GroupMemberForm(group=group),
        "standings": standings,
        "game_type_options": game_type_options,
        "selected_game_type_code": selected_game_type_code,
        "selected_game_type": selected_game_type,
        "show_losses": show_losses,
        "standings_sort": sort,
        "standings_dir": "desc" if not ascending else "asc",
        "player_form": GroupPlayerForm(group=group),
    }


@demo_or_login_required
def group_list(request: HttpRequest) -> HttpResponse:
    groups = visible_groups(request.user).order_by("name")
    return render(
        request,
        "groups/group_list.html",
        {"groups": groups},
    )


@login_required
def group_create(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = GroupForm(request.POST)
        if form.is_valid():
            group = create_group_with_owner(
                user=request.user,
                name=form.cleaned_data["name"],
                description=form.cleaned_data["description"],
            )
            messages.success(request, f'Group "{group.name}" created.')
            return redirect("groups:detail", pk=group.pk)
    else:
        form = GroupForm()

    return render(
        request,
        "groups/group_form.html",
        {"form": form, "title": "Create Group"},
    )


@demo_or_login_required
def group_detail(request: HttpRequest, pk: int) -> HttpResponse:
    group = get_object_or_404(Group, pk=pk)
    if not can_view_group(request.user, group):
        raise Http404

    return render(
        request,
        "groups/group_detail.html",
        _group_detail_context(group, request),
    )


@demo_or_login_required
def group_locations(request: HttpRequest, pk: int) -> JsonResponse:
    group = get_object_or_404(Group, pk=pk)
    if not can_view_group(request.user, group):
        raise Http404

    locations = [
        {"name": location.name}
        for location in locations_for_group(group)
    ]
    return JsonResponse({"locations": locations})


@demo_or_login_required
def group_players_search(request: HttpRequest, pk: int) -> JsonResponse:
    group = get_object_or_404(Group, pk=pk)
    if not can_view_group(request.user, group):
        raise Http404

    query = request.GET.get("q", "")
    players = search_group_players(group, query)
    return JsonResponse({"players": players})


@login_required
def player_add(request: HttpRequest, pk: int) -> HttpResponse:
    group = get_object_or_404(Group, pk=pk)
    if not user_is_member(request.user, group):
        raise Http404

    if request.method != "POST":
        return redirect("groups:detail", pk=group.pk)

    form = GroupPlayerForm(request.POST, group=group)
    if form.is_valid():
        add_guest_player(
            group=group,
            display_name=form.cleaned_data["display_name"],
        )
        messages.success(
            request,
            f'Added {form.cleaned_data["display_name"]} to the group.',
        )
        return redirect("groups:detail", pk=group.pk)

    context = _group_detail_context(group, request)
    context["player_form"] = form
    return render(
        request,
        "groups/group_detail.html",
        context,
        status=400,
    )


@login_required
def member_add(request: HttpRequest, pk: int) -> HttpResponse:
    group = get_object_or_404(Group, pk=pk)
    if not user_is_member(request.user, group):
        raise Http404

    if request.method != "POST":
        return redirect("groups:detail", pk=group.pk)

    form = GroupMemberForm(request.POST, group=group)
    if form.is_valid():
        member = form.cleaned_data["user"]
        add_group_member(group=group, user=member)
        messages.success(
            request,
            f"Added {member.get_username()} as a group member.",
        )
        return redirect("groups:detail", pk=group.pk)

    context = _group_detail_context(group, request)
    context["member_form"] = form
    return render(
        request,
        "groups/group_detail.html",
        context,
        status=400,
    )
