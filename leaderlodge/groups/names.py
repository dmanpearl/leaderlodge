from django.contrib.auth.models import AbstractBaseUser


def format_user_display_name(user: AbstractBaseUser) -> str:
    first = (user.first_name or "").strip()
    last = (user.last_name or "").strip()
    if first and last:
        return f"{first} {last[0]}"
    if first:
        return first
    return user.get_username()
