from urllib.parse import urlparse

from django.contrib.auth.tokens import default_token_generator
from django.template import loader
from django.test import RequestFactory
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from leaderlodge.accounts.email_verification import render_welcome_email


def mock_request(site_url: str):
    parsed = urlparse(site_url)
    host = parsed.netloc or "127.0.0.1:8000"
    factory = RequestFactory()
    request = factory.get("/", HTTP_HOST=host)
    if parsed.scheme == "https":
        request.META["wsgi.url_scheme"] = "https"
    return request


def render_password_reset_email(*, user, request) -> tuple[str, str]:
    site_url = request.build_absolute_uri("/")
    parsed = urlparse(site_url)
    context = {
        "email": user.email,
        "domain": parsed.netloc,
        "site_name": parsed.netloc,
        "uid": urlsafe_base64_encode(force_bytes(user.pk)),
        "user": user,
        "token": default_token_generator.make_token(user),
        "protocol": parsed.scheme,
    }
    subject = loader.render_to_string("accounts/password_reset_subject.txt", context)
    subject = "".join(subject.splitlines())
    body = loader.render_to_string("accounts/password_reset_email.txt", context)
    return subject, body


def render_sample_email(*, email_type: str, user, request) -> tuple[str, str]:
    if email_type == "welcome":
        return render_welcome_email(user=user, request=request)
    if email_type == "password-reset":
        return render_password_reset_email(user=user, request=request)
    raise ValueError(f"Unsupported email type: {email_type}")
