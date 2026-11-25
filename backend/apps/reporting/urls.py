from django.urls import path

from . import views

urlpatterns = [
    path("organizations/", views.list_organizations),
    path("organizations/<int:organization_id>/streams/", views.organization_streams),
    path("organizations/<int:organization_id>/bundles/", views.organization_bundles),
    path("organizations/<int:organization_id>/overview/", views.organization_overview),
    path("organizations/<int:organization_id>/compare/", views.organization_compare),
    path("organizations/<int:organization_id>/export/", views.organization_export),
]
