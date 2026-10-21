from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("apps.core.urls")),
    path("api/participant/", include("apps.participants.urls")),
    path("api/identity/", include("apps.identity.urls")),
    path("api/employer/", include("apps.reporting.urls")),
]
