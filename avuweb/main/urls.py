from django.urls import path

from .views import benefits_partial, landing, profile, signup

app_name = "main"

urlpatterns = [
    path("", landing, name="home"),
    path("signup/", signup, name="signup"),
    path("profile/", profile, name="profile"),
    path("fragments/benefits/", benefits_partial, name="benefits"),
]
