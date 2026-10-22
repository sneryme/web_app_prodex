from django.urls import path

from . import views

urlpatterns = [
    path("clients/", views.list_clients),
    path("licenses/", views.list_licenses),
    path("operations/", views.operations),
]
