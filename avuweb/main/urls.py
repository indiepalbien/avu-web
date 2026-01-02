from django.urls import path

from .views import benefits_partial, landing

app_name = "main"

urlpatterns = [
    path("", landing, name="home"),
    path("fragments/benefits/", benefits_partial, name="benefits"),
]
