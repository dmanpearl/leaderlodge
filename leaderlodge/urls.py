from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("leaderlodge.accounts.urls")),
    path("groups/", include("leaderlodge.groups.urls")),
    path("", include("leaderlodge.core.urls")),
]
