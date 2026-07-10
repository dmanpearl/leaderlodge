from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from leaderlodge.accounts.email_verification import (
    is_email_verified,
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
    CombinePlayersForm,
    GroupForm,
    GroupInviteEmailForm,
    GuestInviteEmailForm,
    InviteAcceptForm,
    GroupPlayerForm,
    LocationRenameForm,
    LocationCombineForm,
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
from leaderlodge.groups.models import Group, GroupMembership, GroupPlayer, Location
from leaderlodge.groups.player_search import search_group_players
from leaderlodge.groups.permissions import (
    can_combine_players,
    can_invite_roster_player,
    can_manage_members,
    can_remove_membership,
    can_set_membership_role,
    get_membership,
    role_choice_options,
    roster_remove_state,
)
from leaderlodge.groups.player_combine import combine_players, preview_combine_players
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
        group.memberships.select_related("user", "user__profile").order_by(
            "user__username"
        )
    )
    actor_membership = get_membership(request.user, group)
    can_manage_members = can_manage_group_members(request.user, group)
    can_combine = can_combine_players(request.user, group)
    show_member_actions = can_manage_members or can_combine
    show_roster_actions = can_manage_members or can_combine
    players_by_user_id = {
        player.linked_user_id: player
        for player in group.players.filter(
            is_active=True,
            linked_user_id__isnull=False,
        )
    }
    verified_user_pks = {m.user_id for m in memberships if is_email_verified(m.user)}
    member_rows = []
    for membership in memberships:
        group_player = players_by_user_id.get(membership.user_id)
        can_combine_member = (
            can_combine and group_player is not None and not group_player.is_team
        )
        if can_manage_members and actor_membership is not None:
            choices = role_choice_options(actor_membership, membership)
            can_remove = can_remove_membership(actor_membership, membership)
        else:
            choices = []
            can_remove = False
        member_rows.append(
            {
                "membership": membership,
                "role_choices": choices,
                "can_remove": can_remove,
                "can_combine": can_combine_member,
                "group_player": group_player,
                "email_verified": membership.user_id in verified_user_pks,
            }
        )
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
                    "can_combine": can_combine and not row.player.is_team,
                    "email_verified": (
                        row.player.linked_user_id in verified_user_pks
                        if row.player.linked_user_id
                        else False
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
                    "can_combine": can_combine and not player.is_team,
                    "email_verified": (
                        player.linked_user_id in verified_user_pks
                        if player.linked_user_id
                        else False
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

    invite_guests = (
        list(
            group.players.filter(
                is_active=True,
                linked_user__isnull=True,
                is_team=False,
            )
            .values("pk", "display_name")
            .order_by("display_name")
        )
        if can_manage_members
        else []
    )
    return {
        "group": group,
        "member_rows": member_rows,
        "can_manage_members": can_manage_members,
        "can_combine_players": can_combine,
        "show_member_actions": show_member_actions,
        "show_roster_actions": show_roster_actions,
        "pending_invites": (
            list(pending_invites_for_group(group)) if can_manage_members else []
        ),
        "invite_guests": [
            {"id": g["pk"], "name": g["display_name"]} for g in invite_guests
        ],
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
        guest_player = form.cleaned_data.get("guest_player")
        try:
            if guest_player is not None:
                invite = create_email_invite_for_guest(
                    group=group,
                    guest_player=guest_player,
                    email=form.cleaned_data["email"],
                    invited_by=request.user,
                )
                success_msg = f"Invitation sent to {invite.email} for {guest_player.display_name}."
            else:
                invite = create_email_invite(
                    group=group,
                    email=form.cleaned_data["email"],
                    invited_by=request.user,
                    player_name=form.cleaned_data.get("player_name", ""),
                )
                success_msg = (
                    f"Invitation sent to {invite.email}. "
                    f"They were added to the roster as a guest until they accept."
                )
            try:
                send_invite_email(request=request, invite=invite)
                messages.success(request, success_msg)
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
                from leaderlodge.accounts.auth_log import record_auth_event
                from leaderlodge.accounts.models import AuthEvent
                from leaderlodge.core.admin_notifications import notify_admin_signup

                signup_event = record_auth_event(
                    event_type=AuthEvent.EventType.SIGNUP,
                    request=request,
                    user=user,
                    email=user.email or "",
                    source="invite_join",
                )
                notify_admin_signup(user=user, event=signup_event)
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
                        request=request,
                    )
                    persist_group_id(request, group.pk)
                    messages.success(request, f'You joined "{group.name}".')
                    return redirect("groups:detail", pk=group.pk)
                except ValueError as exc:
                    messages.error(request, str(exc))
            else:
                from leaderlodge.accounts.auth_log import log_failed_signup

                log_failed_signup(request, join_form, source="invite_join")
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
                        request=request,
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


@login_required
def player_combine(request: HttpRequest, pk: int, player_pk: int) -> HttpResponse:
    group = get_object_or_404(Group, pk=pk)
    keeper = get_object_or_404(
        GroupPlayer.objects.select_related("linked_user"),
        pk=player_pk,
        group=group,
        is_active=True,
        is_team=False,
    )
    if not can_combine_players(request.user, group):
        raise Http404

    cancel_url = reverse("groups:detail", kwargs={"pk": group.pk})

    if request.method == "POST" and request.POST.get("confirm") == "yes":
        source = get_object_or_404(
            GroupPlayer,
            pk=int(request.POST.get("source", "0")),
            group=group,
            is_active=True,
            is_team=False,
        )
        try:
            preview = combine_players(keeper=keeper, source=source)
        except ValueError as exc:
            messages.error(request, str(exc))
            return redirect(cancel_url)
        messages.success(
            request,
            f'Combined "{preview.source.display_label}" into '
            f'"{preview.keeper.display_label}".',
        )
        return redirect(cancel_url)

    if request.method == "POST":
        form = CombinePlayersForm(request.POST, group=group, keeper=keeper)
        if form.is_valid():
            source = form.cleaned_data["source"]
            preview = preview_combine_players(keeper=keeper, source=source)
            return render(
                request,
                "groups/player_combine_confirm.html",
                {
                    "group": group,
                    "source": source,
                    "keeper": keeper,
                    "preview": preview,
                    "cancel_url": cancel_url,
                },
            )
    else:
        form = CombinePlayersForm(group=group, keeper=keeper)

    return render(
        request,
        "groups/player_combine.html",
        {
            "group": group,
            "keeper": keeper,
            "form": form,
            "cancel_url": cancel_url,
        },
    )


@login_required
def location_manage(request: HttpRequest, pk: int) -> HttpResponse:
    from django.db.models import Count, Max

    from leaderlodge.accounts.ui_settings import get_ui_settings, set_ui_settings
    from leaderlodge.games.models import Game
    from leaderlodge.games.registry import GAME_TYPES
    from leaderlodge.groups.locations import (
        GAME_CODE_SHORT,
        ensure_group_location_library,
    )

    group = get_object_or_404(Group, pk=pk)
    if not can_manage_group_members(request.user, group):
        raise Http404

    valid_fields = {"name", "count", "date"}
    valid_dirs = {"asc", "desc"}
    prefs = get_ui_settings(request.user, "location_list")

    if "sort" in request.GET or "dir" in request.GET:
        sort_field = request.GET.get("sort", prefs.get("sort_field", "name"))
        sort_dir = request.GET.get("dir", prefs.get("sort_dir", "asc"))
        if sort_field not in valid_fields:
            sort_field = "name"
        if sort_dir not in valid_dirs:
            sort_dir = "asc"
        set_ui_settings(
            request.user,
            "location_list",
            {"sort_field": sort_field, "sort_dir": sort_dir},
        )
    else:
        sort_field = prefs.get("sort_field", "name")
        sort_dir = prefs.get("sort_dir", "asc")
        if sort_field not in valid_fields:
            sort_field = "name"
        if sort_dir not in valid_dirs:
            sort_dir = "asc"

    _sort_map = {
        "name": "name",
        "count": "game_count",
        "date": "last_played",
    }
    orm_field = _sort_map[sort_field]
    if sort_dir == "desc":
        orm_field = f"-{orm_field}"

    library = ensure_group_location_library(group)
    locations_qs = library.locations.annotate(
        game_count=Count("games"),
        last_played=Max("games__played_on"),
    ).order_by(orm_field, "name")

    game_type_map: dict[int, list[str]] = {}
    for row in (
        Game.objects.filter(location__library=library)
        .values("location_id", "game_type_code")
        .distinct()
    ):
        game_type_map.setdefault(row["location_id"], []).append(row["game_type_code"])

    location_rows = []
    location_data = []
    for loc in locations_qs:
        seen_codes: set[str] = set()
        game_pills = []
        for c in sorted(game_type_map.get(loc.pk, [])):
            short = GAME_CODE_SHORT.get(c, c[:2].upper())
            if short in seen_codes:
                continue
            seen_codes.add(short)
            full_name = GAME_TYPES[c].name if c in GAME_TYPES else c
            game_pills.append({"code": short, "name": full_name})
        game_pills.sort(key=lambda p: p["code"])
        location_rows.append(
            {
                "location": loc,
                "game_count": loc.game_count,
                "last_played": loc.last_played,
                "game_pills": game_pills,
            }
        )
        location_data.append({"pk": loc.pk, "name": loc.name})

    return render(
        request,
        "groups/location_list.html",
        {
            "group": group,
            "location_rows": location_rows,
            "location_data": location_data,
            "sort_field": sort_field,
            "sort_dir": sort_dir,
        },
    )


@login_required
def location_rename(request: HttpRequest, pk: int, loc_pk: int) -> HttpResponse:
    from leaderlodge.groups.locations import (
        ensure_group_location_library,
        rename_location,
    )

    group = get_object_or_404(Group, pk=pk)
    if not can_manage_group_members(request.user, group):
        raise Http404
    if request.method != "POST":
        return redirect("groups:location_manage", pk=group.pk)

    library = ensure_group_location_library(group)
    location = get_object_or_404(Location, pk=loc_pk, library=library)
    form = LocationRenameForm(request.POST, location=location)
    if form.is_valid():
        try:
            rename_location(location=location, new_name=form.cleaned_data["name"])
            messages.success(request, f'Location renamed to "{location.name}".')
        except Exception as exc:
            messages.error(request, str(exc))
    else:
        errors = form.errors.get("name", form.non_field_errors())
        if errors:
            messages.error(request, errors[0])
    return redirect("groups:location_manage", pk=group.pk)


@login_required
def location_combine(request: HttpRequest, pk: int, loc_pk: int) -> HttpResponse:
    from leaderlodge.groups.locations import (
        combine_locations,
        ensure_group_location_library,
    )

    group = get_object_or_404(Group, pk=pk)
    if not can_manage_group_members(request.user, group):
        raise Http404
    if request.method != "POST":
        return redirect("groups:location_manage", pk=group.pk)

    library = ensure_group_location_library(group)
    keeper = get_object_or_404(Location, pk=loc_pk, library=library)
    form = LocationCombineForm(request.POST, keeper=keeper)
    if form.is_valid():
        source = form.cleaned_data["source"]
        try:
            count = combine_locations(keeper=keeper, source=source)
            messages.success(
                request,
                f'Merged "{source.name}" into "{keeper.name}" '
                f'({count} game{"s" if count != 1 else ""} updated).',
            )
        except Exception as exc:
            messages.error(request, str(exc))
    else:
        messages.error(request, "Could not combine locations.")
    return redirect("groups:location_manage", pk=group.pk)


@login_required
def location_delete(request: HttpRequest, pk: int, loc_pk: int) -> HttpResponse:
    from leaderlodge.groups.locations import ensure_group_location_library

    group = get_object_or_404(Group, pk=pk)
    if not can_manage_group_members(request.user, group):
        raise Http404
    if request.method != "POST":
        return redirect("groups:location_manage", pk=group.pk)

    library = ensure_group_location_library(group)
    location = get_object_or_404(Location, pk=loc_pk, library=library)
    if location.games.exists():
        messages.error(request, f'"{location.name}" has games and cannot be deleted.')
        return redirect("groups:location_manage", pk=group.pk)

    name = location.name
    location.delete()
    messages.success(request, f'Deleted "{name}".')
    return redirect("groups:location_manage", pk=group.pk)
