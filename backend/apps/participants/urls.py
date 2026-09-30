from django.urls import path

from . import views

urlpatterns = [
    path("sessions/", views.create_session),
    path("sessions/<str:token>/", views.session_detail),
    path("sessions/<str:token>/consents/", views.session_consent),
    path("sessions/<str:token>/answers/", views.session_answer),
    path("reports/<str:token>/", views.session_report),
]
