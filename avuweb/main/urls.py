from django.urls import path

from .views import benefits_partial, landing, profile, signup, static_page, mercado_pago_webhook

app_name = "main"

urlpatterns = [
    path("", landing, name="home"),
    path("signup/", signup, name="signup"),
    path("profile/", profile, name="profile"),
    path("fragments/benefits/", benefits_partial, name="benefits"),
    path("pages/<slug:slug>/", static_page, name="static_page"),
    # Webhooks
    path("webhooks/mercado-pago/", mercado_pago_webhook, name="mp_webhook"),
]
