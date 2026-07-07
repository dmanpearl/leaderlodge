from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from leaderlodge.accounts.email_verification import (
    record_verification_email_sent,
    send_welcome_email,
)
from leaderlodge.accounts.forms import InviteJoinSignupForm
from leaderlodge.accounts.honeypot import handle_signup_honeypot
from leaderlodge.accounts.game_selection import resolve_game_type_code
from leaderlodge.core.decorators import demo_or_login_required
from leaderlodge.games.registry import get_game_type
from leaderlodge.accounts.group_selection import persist_group_id
from leaderlodge.groups.forms import (
    GroupForm,
    GroupInviteEmailForm,
    GuestInviteEmailForm,
    InviteAcceptForm,
    GroupPlayerForm,
)
from leaderlodge.groups.invites import (
    accept_group_invite,
    create_email_invite,
    create_email_invite_for_guest,
    default_first_name_for_invite,
    invite_email_matches_user,
    invite_for_token,
    pending_invites_for_group,
    revoke_group_invite,
    send_invite_email,
)
from leaderlodge.groups.locations import locations_for_group
from leaderlodge.groups.models import Group, GroupMembership, GroupPlayer
from leaderlodge.groups.player_search import search_group_players
from leaderlodge.groups.permissions import (
    can_invite_roster_player,
    can_manage_members,
    can_remove_membership,
    can_set_membership_role,
    get_membership,
    role_choice_options,
    roster_remove_state,
)
from leaderlodge.groups.services import (
    add_guest_player,
    can_manage_group_members,
    can_view_group,
    create_group_with_owner,
    remove_group_member,
    remove_roster_player,
    user_is_member,
    visible_groups,
)
from leaderlodge.leaderboards.period import (
    available_leaderboard_periods,
    build_leaderboard_query,
    month_label,
    resolve_leaderboard_period,
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
    memberships = list(
        group.memberships.select_related("user").order_by("user__username")
    )
    actor_membership = get_membership(request.user, group)
    can_manage_members = can_manage_group_members(request.user, group)
    member_rows = []
    if can_manage_members and actor_membership is not None:
        for membership in memberships:
            choices = role_choice_options(actor_membership, membership)
            member_rows.append(
                {
                    "membership": membership,
                    "role_choices": choices,
                    "can_remove": can_remove_membership(actor_membership, membership),
                }
            )
    else:
        member_rows = [
            {
                "membership": membership,
                "role_choices": [],
                "can_remove": False,
            }
            for membership in memberships
        ]
    game_type_codes = _game_type_codes_for_group(group)
    if game_type_codes:
        selected_game_type_code = resolve_game_type_code(
            request,
            requested=request.GET.get("game_type_code", "").strip(),
            available_codes=game_type_codes,
        )
    else:
        selected_game_type_code = None

    years, months_by_year = (
        available_leaderboard_periods(group, selected_game_type_code)
        if selected_game_type_code
        else ([], {})
    )
    selected_period = resolve_leaderboard_period(
        raw_year=request.GET.get("year", "").strip(),
        raw_month=request.GET.get("month", "").strip(),
        available_years=years,
        months_by_year=months_by_year,
    )
    period_month_options = [
        {"value": month, "label": month_label(month)}
        for month in (
            months_by_year.get(selected_period.year, ())
            if selected_period.year is not None
            else ()
        )
    ]

    sort = request.GET.get("sort", "rank")
    if sort not in SORTABLE_COLUMNS:
        sort = "rank"
    ascending = request.GET.get("dir", "asc") != "desc"

    standings = []
    standings_rows = []
    roster_players = []
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
            period=selected_period,
        )
        for row in standings:
            remove_state = roster_remove_state(actor_membership, row.player, group)
            standings_rows.append(
                {
                    "standing": row,
                    "can_invite": can_invite_roster_player(
                        actor_membership, row.player, group
                    ),
                    **remove_state,
                }
            )
    else:
        for player in group.players.filter(is_active=True).select_related(
            "linked_user"
        ):
            remove_state = roster_remove_state(actor_membership, player, group)
            roster_players.append(
                {
                    "player": player,
                    "can_invite": can_invite_roster_player(
                        actor_membership, player, group
                    ),
                    **remove_state,
                }
            )

    game_type_options = [(code, get_game_type(code).name) for code in game_type_codes]
    filter_query = build_leaderboard_query(
        game_type_code=selected_game_type_code or "",
        period=selected_period,
    )
    player_detail_query = (
        build_leaderboard_query(
            group_id=str(group.pk),
            game_type_code=selected_game_type_code,
            period=selected_period,
        )
        if selected_game_type_code
        else ""
    )

    return {
        "group": group,
        "member_rows": member_rows,
        "can_manage_members": can_manage_members,
        "pending_invites": (
            list(pending_invites_for_group(group)) if can_manage_members else []
        ),
        "invite_form": GroupInviteEmailForm(group=group),
        "standings": standings,
        "standings_rows": standings_rows,
        "roster_players": roster_players,
        "game_type_options": game_type_options,
        "selected_game_type_code": selected_game_type_code,
        "selected_game_type": selected_game_type,
        "show_losses": show_losses,
        "standings_sort": sort,
        "standings_dir": "desc" if not ascending else "asc",
        "filter_query": filter_query,
        "player_detail_query": player_detail_query,
        "selected_period": selected_period,
        "period_year_options": years,
        "period_month_options": period_month_options,
        "period_label": selected_period.display_label(),
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
            persist_group_id(request, group.pk)
            messages.success(request, f'Group "{group.name}" created.')
            return redirect("groups:detail", pk=group.pk)
    else:
        form = GroupForm()

    return render(
        request,
        "groups/group_form.html",
        {
            "form": form,
            "title": "Create Group",
            "cancel_url": reverse("groups:list"),
        },
    )


@login_required
def group_edit(request: HttpRequest, pk: int) -> HttpResponse:
    group = get_object_or_404(Group, pk=pk)
    if not can_manage_group_members(request.user, group):
        raise Http404

    if request.method == "POST":
        form = GroupForm(request.POST, instance=group)
        if form.is_valid():
            form.save()
            messages.success(request, f'Group "{group.name}" updated.')
            return redirect("groups:detail", pk=group.pk)
    else:
        form = GroupForm(instance=group)

    return render(
        request,
        "groups/group_form.html",
        {
            "form": form,
            "title": "Edit Group",
            "cancel_url": reverse("groups:detail", kwargs={"pk": group.pk}),
        },
    )


@demo_or_login_required
def group_detail(request: HttpRequest, pk: int) -> HttpResponse:
    group = get_object_or_404(Group, pk=pk)
    if not can_view_group(request.user, group):
        raise Http404

    if request.user.is_authenticated:
        persist_group_id(request, group.pk)

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

    locations = [{"name": location.name} for location in locations_for_group(group)]
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
    if not can_manage_group_members(request.user, group):
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
def invite_send(request: HttpRequest, pk: int) -> HttpResponse:
    group = get_object_or_404(Group, pk=pk)
    if not can_manage_group_members(request.user, group):
        raise Http404

    if request.method != "POST":
        return redirect("groups:detail", pk=group.pk)

    form = GroupInviteEmailForm(request.POST, group=group)
    if form.is_valid():
        try:
            invite = create_email_invite(
                group=group,
                email=form.cleaned_data["email"],
                invited_by=request.user,
                player_name=form.cleaned_data.get("player_name", ""),
            )
            try:
                send_invite_email(request=request, invite=invite)
                messages.success(
                    request,
                    f"Invitation sent to {invite.email}. "
                    f"They were added to the roster as a guest until they accept.",
                )
            except Exception:
                messages.warning(
                    request,
                    f"Invite created for {invite.email}, but the email could not be sent. "
                    "Ask them to use the link from a previous message or resend the invite.",
                )
            return redirect("groups:detail", pk=group.pk)
        except ValueError as exc:
            form.add_error(None, str(exc))

    context = _group_detail_context(group, request)
    context["invite_form"] = form
    return render(
        request,
        "groups/group_detail.html",
        context,
        status=400,
    )


@login_required
def player_invite(request: HttpRequest, pk: int, player_pk: int) -> HttpResponse:
    group = get_object_or_404(Group, pk=pk)
    player = get_object_or_404(GroupPlayer, pk=player_pk, group=group)
    actor_membership = get_membership(request.user, group)
    if actor_membership is None or not can_invite_roster_player(
        actor_membership, player, group
    ):
        raise Http404

    if request.method != "POST":
        return redirect("groups:detail", pk=group.pk)

    form = GuestInviteEmailForm(request.POST, group=group)
    if form.is_valid():
        try:
            invite = create_email_invite_for_guest(
                group=group,
                guest_player=player,
                email=form.cleaned_data["email"],
                invited_by=request.user,
            )
            try:
                send_invite_email(request=request, invite=invite)
                messages.success(
                    request,
                    f"Invitation sent to {invite.email} for {player.display_name}.",
                )
            except Exception:
                messages.warning(
                    request,
                    f"Invite created for {invite.email}, but the email could not be sent.",
                )
        except ValueError as exc:
            messages.error(request, str(exc))
    else:
        for error in form.errors.get("email", []):
            messages.error(request, error)

    return redirect("groups:detail", pk=group.pk)


@login_required
def invite_revoke(request: HttpRequest, pk: int, invite_pk: int) -> HttpResponse:
    group = get_object_or_404(Group, pk=pk)
    if not can_manage_group_members(request.user, group):
        raise Http404

    if request.method != "POST":
        return redirect("groups:detail", pk=group.pk)

    from leaderlodge.groups.models import GroupInvite

    invite = get_object_or_404(GroupInvite, pk=invite_pk, group=group)
    revoke_group_invite(invite=invite)
    messages.success(request, "Invite revoked.")
    return redirect("groups:detail", pk=group.pk)


def invite_accept(request: HttpRequest, token: str) -> HttpResponse:
    invite = invite_for_token(token)
    if invite is None or not invite.is_pending:
        return render(
            request,
            "groups/invite_accept.html",
            {"invite": None, "invalid": True},
            status=404,
        )

    group = invite.group
    accept_url = reverse("groups:invite_accept", kwargs={"token": token})
    login_url = f"{reverse('accounts:login')}?next={accept_url}"

    default_first_name = default_first_name_for_invite(invite)
    join_form = InviteJoinSignupForm(
        initial={"first_name": default_first_name},
        invite=invite,
    )
    accept_form = InviteAcceptForm(initial={"first_name": default_first_name})
    session_match = "anonymous"
    if request.user.is_authenticated:
        if user_is_member(request.user, group):
            session_match = "member"
        elif invite_email_matches_user(invite, request.user):
            session_match = "match"
        else:
            session_match = "mismatch"

    if request.method == "POST":
        if not request.user.is_authenticated:
            join_form = InviteJoinSignupForm(request.POST, invite=invite)
            if handle_signup_honeypot(
                request,
                source="invite_join",
                post_data=request.POST,
                form=join_form,
            ):
                session_match = "anonymous"
            elif join_form.is_valid():
                user = join_form.save()
                login(request, user)
                from leaderlodge.core.admin_notifications import notify_admin_signup

                notify_admin_signup(user=user)
                try:
                    send_welcome_email(request=request, user=user)
                    record_verification_email_sent(user)
                    messages.success(
                        request,
                        "Welcome to LeaderLodge! We sent a confirmation link to your email.",
                    )
                except Exception:
                    messages.warning(
                        request,
                        "Your account was created, but we could not send the welcome email. "
                        "Use Verify Email in the account menu to try again.",
                    )
                try:
                    accept_group_invite(
                        invite=invite,
                        user=user,
                        first_name=user.first_name,
                        last_name=user.last_name,
                    )
                    persist_group_id(request, group.pk)
                    messages.success(request, f'You joined "{group.name}".')
                    return redirect("groups:detail", pk=group.pk)
                except ValueError as exc:
                    messages.error(request, str(exc))
            session_match = "anonymous"
        else:
            accept_form = InviteAcceptForm(request.POST)
            if accept_form.is_valid():
                try:
                    if not invite_email_matches_user(invite, request.user):
                        messages.error(
                            request,
                            f"This invite was sent to {invite.email}. "
                            "Sign in with that email to accept.",
                        )
                        return redirect("groups:invite_accept", token=token)
                    accept_group_invite(
                        invite=invite,
                        user=request.user,
                        first_name=accept_form.cleaned_data["first_name"],
                        last_name=accept_form.cleaned_data.get("last_name", ""),
                    )
                    persist_group_id(request, group.pk)
                    messages.success(request, f'You joined "{group.name}".')
                    return redirect("groups:detail", pk=group.pk)
                except ValueError as exc:
                    messages.error(request, str(exc))
            session_match = "match"

    return render(
        request,
        "groups/invite_accept.html",
        {
            "invite": invite,
            "group": group,
            "invalid": False,
            "session_match": session_match,
            "login_url": login_url,
            "accept_url": accept_url,
            "accept_form": accept_form,
            "join_form": join_form,
        },
    )


@login_required
def member_update_role(
    request: HttpRequest, pk: int, membership_pk: int
) -> HttpResponse:
    group = get_object_or_404(Group, pk=pk)
    membership = get_object_or_404(GroupMembership, pk=membership_pk, group=group)
    actor_membership = get_membership(request.user, group)
    if actor_membership is None or not can_manage_members(actor_membership):
        raise Http404

    if request.method != "POST":
        return redirect("groups:detail", pk=group.pk)

    new_role = request.POST.get("role", "")
    if can_set_membership_role(actor_membership, membership, new_role):
        membership.role = new_role
        membership.save(update_fields=["role"])
        messages.success(
            request,
            f"Updated {membership.user.get_username()} to "
            f"{membership.get_role_display()}.",
        )
    else:
        messages.error(request, "You cannot change this member's role.")

    return redirect("groups:detail", pk=group.pk)


@login_required
def member_remove(request: HttpRequest, pk: int, membership_pk: int) -> HttpResponse:
    group = get_object_or_404(Group, pk=pk)
    membership = get_object_or_404(GroupMembership, pk=membership_pk, group=group)
    actor_membership = get_membership(request.user, group)
    if actor_membership is None or not can_manage_members(actor_membership):
        raise Http404

    if request.method != "POST":
        return redirect("groups:detail", pk=group.pk)

    username = membership.user.get_username()
    if can_remove_membership(actor_membership, membership):
        outcome = remove_group_member(membership=membership)
        if outcome == "converted":
            messages.success(
                request,
                f"Removed {username} from the group. They remain on the roster as a "
                "guest player for past games.",
            )
        else:
            messages.success(request, f"Removed {username} from the group.")
    else:
        messages.error(request, f"You cannot remove {username} from the group.")

    return redirect("groups:detail", pk=group.pk)


@login_required
def player_remove(request: HttpRequest, pk: int, player_pk: int) -> HttpResponse:
    group = get_object_or_404(Group, pk=pk)
    player = get_object_or_404(GroupPlayer, pk=player_pk, group=group)
    actor_membership = get_membership(request.user, group)
    remove_state = roster_remove_state(actor_membership, player, group)
    if (
        actor_membership is None
        or not remove_state["can_remove"]
        or remove_state["remove_url_name"] != "groups:player_remove"
    ):
        raise Http404

    if request.method != "POST":
        return redirect("groups:detail", pk=group.pk)

    name = player.display_label
    try:
        remove_roster_player(player=player)
    except ValueError:
        raise Http404 from None
    messages.success(request, f"Removed {name} from the roster.")
    return redirect("groups:detail", pk=group.pk)
