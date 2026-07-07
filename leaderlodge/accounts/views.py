from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.middleware.csrf import get_token
from django.shortcuts import redirect, render
from django.utils.http import urlsafe_base64_decode
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from leaderlodge.accounts.email_verification import (
    email_verification_token_generator,
    is_email_verified,
    mark_email_verified,
    record_verification_email_sent,
    send_welcome_email,
    should_auto_send_verification,
    verification_email_pending,
)
from leaderlodge.accounts.auth_log import log_failed_signup
from leaderlodge.accounts.forms import SignupForm
from leaderlodge.accounts.honeypot import handle_signup_honeypot
from leaderlodge.accounts.game_selection import SESSION_GAME_TYPE_CODE
from leaderlodge.accounts.group_selection import SESSION_GROUP_ID
from leaderlodge.accounts.ui_settings import reset_ui_settings
from leaderlodge.accounts.group_selection import persist_group_id
from leaderlodge.groups.invites import (
    accept_group_invite,
    default_first_name_for_invite,
    invite_for_token,
)
from leaderlodge.groups.models import GroupInvite
from leaderlodge.groups.names import format_user_display_name


@require_GET
@ensure_csrf_cookie
def csrf_token(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"csrfToken": get_token(request)})


@login_required
@require_POST
def reset_preferences(request: HttpRequest) -> JsonResponse:
    reset_ui_settings(request.user)
    request.session.pop(SESSION_GAME_TYPE_CODE, None)
    request.session.pop(SESSION_GROUP_ID, None)
    return JsonResponse({"ok": True})


@require_http_methods(["GET", "POST"])
def signup(request: HttpRequest) -> HttpResponse:
    invite_token = (
        request.GET.get("invite", "").strip()
        or request.POST.get("invite_token", "").strip()
    )
    invite = invite_for_token(invite_token) if invite_token else None
    if invite is not None and not invite.is_pending:
        invite = None

    if request.user.is_authenticated:
        if invite is not None:
            return redirect("groups:invite_accept", token=invite.token)
        return redirect("core:dashboard")

    lock_email = invite is not None
    invite_first_name = default_first_name_for_invite(invite) if invite else ""
    form = SignupForm(
        request.POST or None,
        invite_email=invite.email if lock_email else "",
        lock_email=lock_email,
        invite_first_name=invite_first_name,
    )
    if request.method == "POST":
        if handle_signup_honeypot(
            request,
            source="signup",
            post_data=request.POST,
            form=form,
        ):
            return render(
                request,
                "accounts/signup.html",
                {
                    "form": form,
                    "invite": invite,
                    "invite_token": invite.token if invite else "",
                },
            )
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        from leaderlodge.accounts.auth_log import record_auth_event
        from leaderlodge.accounts.models import AuthEvent
        from leaderlodge.core.admin_notifications import notify_admin_signup

        signup_event = record_auth_event(
            event_type=AuthEvent.EventType.SIGNUP,
            request=request,
            user=user,
            email=user.email or "",
            source="invite_join" if invite is not None else "signup",
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
        if invite is not None:
            try:
                accept_group_invite(
                    invite=invite,
                    user=user,
                    first_name=user.first_name,
                    last_name=user.last_name,
                    request=request,
                )
                persist_group_id(request, invite.group_id)
                messages.success(request, f'You joined "{invite.group.name}".')
                return redirect("groups:detail", pk=invite.group_id)
            except ValueError as exc:
                messages.error(request, str(exc))
        return redirect("core:dashboard")

    if request.method == "POST":
        log_failed_signup(
            request,
            form,
            source="invite_join" if invite is not None else "signup",
        )

    return render(
        request,
        "accounts/signup.html",
        {
            "form": form,
            "invite": invite,
            "invite_token": invite.token if invite else "",
        },
    )


def _user_from_uidb64(uidb64: str) -> User | None:
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        return User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        return None


def _verify_email_confirm_context(
    request: HttpRequest,
    verified_user: User,
    *,
    already_verified: bool,
) -> dict:
    if request.user.is_authenticated:
        session_match = "same" if request.user.pk == verified_user.pk else "different"
    else:
        session_match = "anonymous"

    return {
        "verified_user": verified_user,
        "verified_display_name": format_user_display_name(verified_user),
        "verified_email": verified_user.email,
        "already_verified": already_verified,
        "session_match": session_match,
        "session_display_name": (
            format_user_display_name(request.user)
            if request.user.is_authenticated
            else ""
        ),
    }


def _render_verify_email_complete(
    request: HttpRequest,
    verified_user: User,
    *,
    already_verified: bool,
) -> HttpResponse:
    return render(
        request,
        "accounts/verify_email_complete.html",
        _verify_email_confirm_context(
            request,
            verified_user,
            already_verified=already_verified,
        ),
    )


@require_GET
def verify_email_confirm(request: HttpRequest, uidb64: str, token: str) -> HttpResponse:
    user = _user_from_uidb64(uidb64)
    if user is None or not email_verification_token_generator.check_token(user, token):
        return render(request, "accounts/verify_email_invalid.html", status=400)

    if is_email_verified(user):
        return _render_verify_email_complete(request, user, already_verified=True)

    mark_email_verified(user)
    from leaderlodge.accounts.auth_log import record_auth_event
    from leaderlodge.accounts.models import AuthEvent

    record_auth_event(
        event_type=AuthEvent.EventType.EMAIL_VERIFIED,
        request=request,
        user=user,
        email=user.email or "",
        source="verify_email",
    )
    return _render_verify_email_complete(request, user, already_verified=False)


@require_POST
def verify_email_sign_in(request: HttpRequest) -> HttpResponse:
    username = request.POST.get("username", "").strip()
    logout(request)
    if username:
        messages.info(
            request,
            f"Sign in as {username} to see your verified status.",
        )
    return redirect("accounts:login")


@login_required
@require_GET
def profile(request: HttpRequest) -> HttpResponse:
    from leaderlodge.groups.services import user_groups

    return render(
        request,
        "accounts/profile.html",
        {
            "email_verified": is_email_verified(request.user),
            "group_count": user_groups(request.user).count(),
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def verify_email(request: HttpRequest) -> HttpResponse:
    if is_email_verified(request.user):
        return render(request, "accounts/verify_email.html", {"verified": True})

    should_send = request.method == "POST" or should_auto_send_verification(
        request.user
    )
    if should_send:
        try:
            send_welcome_email(request=request, user=request.user)
            record_verification_email_sent(request.user)
            if request.method == "POST":
                messages.success(
                    request,
                    "We sent another confirmation link to your email address.",
                )
        except ValueError:
            messages.error(
                request,
                "Your account does not have an email address on file.",
            )
        except Exception:
            messages.error(
                request,
                "We could not send the email right now. Please try again in a few minutes.",
            )
        if request.method == "POST":
            return redirect("accounts:verify_email")

    return render(
        request,
        "accounts/verify_email.html",
        {
            "verified": False,
            "email_pending": verification_email_pending(request.user),
        },
    )
