from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path

from leaderlodge.core.sitemaps import StaticPageSitemap
from leaderlodge.core.views import robots_txt

_sitemaps = {
    "static": StaticPageSitemap,
}

urlpatterns = [
    path("robots.txt", robots_txt),
    path(
        "sitemap.xml",
        sitemap,
        {"sitemaps": _sitemaps},
        name="django.contrib.sitemaps.views.sitemap",
    ),
    path("admin/", admin.site.urls),
    path("accounts/", include("leaderlodge.accounts.urls")),
    path("groups/", include("leaderlodge.groups.urls")),
    path("games/", include("leaderlodge.games.urls")),
    path("leaderboards/", include("leaderlodge.leaderboards.urls")),
    path("insights/", include("leaderlodge.insights.urls")),
    path("feedback/", include("leaderlodge.feedback.urls")),
    path("", include("leaderlodge.core.urls")),
]
