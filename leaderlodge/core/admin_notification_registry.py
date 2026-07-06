"""Registry of admin notification types (JSON keys in SiteSettings.notifications)."""

NOTIFICATION_LABELS: dict[str, str] = {
    "signup": "New user signup",
    "invite_sent": "Group invite sent",
    "invite_accepted": "Group invite accepted",
    "game_change": "Game edited (change log)",
    "feedback": "Feedback submitted",
}

DEFAULT_NOTIFICATIONS: dict[str, bool] = {key: True for key in NOTIFICATION_LABELS}
