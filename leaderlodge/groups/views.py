from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from leaderlodge.groups.forms import GroupForm, GroupPlayerForm
from leaderlodge.groups.models import Group
from leaderlodge.groups.services import (
    add_guest_player,
    create_group_with_owner,
    user_groups,
    user_is_member,
)


@login_required
def group_list(request: HttpRequest) -> HttpResponse:
    groups = user_groups(request.user).order_by("name")
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


@login_required
def group_detail(request: HttpRequest, pk: int) -> HttpResponse:
    group = get_object_or_404(Group, pk=pk)
    if not user_is_member(request.user, group):
        raise Http404

    players = group.players.filter(is_active=True).select_related("linked_user")
    player_form = GroupPlayerForm(group=group)

    return render(
        request,
        "groups/group_detail.html",
        {
            "group": group,
            "players": players,
            "player_form": player_form,
        },
    )


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

    players = group.players.filter(is_active=True).select_related("linked_user")
    return render(
        request,
        "groups/group_detail.html",
        {
            "group": group,
            "players": players,
            "player_form": form,
        },
        status=400,
    )
