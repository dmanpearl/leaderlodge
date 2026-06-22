from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "leaderlodge.accounts"
    label = "accounts"

    def ready(self):
        import leaderlodge.accounts.models  # noqa: F401
