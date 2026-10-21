from django.urls import path

from . import views

urlpatterns = [
    path("organizations/", views.list_organizations),
    path("organizations/<int:organization_id>/streams/", views.organization_streams),
    path("organizations/<int:organization_id>/overview/", views.organization_overview),
    path("organizations/<int:organization_id>/export/", views.organization_export),
]
