from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("leaderlodge.accounts.urls")),
    path("groups/", include("leaderlodge.groups.urls")),
    path("games/", include("leaderlodge.games.urls")),
    path("leaderboards/", include("leaderlodge.leaderboards.urls")),
    path("insights/", include("leaderlodge.insights.urls")),
    path("feedback/", include("leaderlodge.feedback.urls")),
    path("", include("leaderlodge.core.urls")),
]
