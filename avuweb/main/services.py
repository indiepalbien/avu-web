import logging
import requests
from django.conf import settings


logger = logging.getLogger(__name__)


class MPException(Exception):
    """Excepción personalizada para errores de Mercado Pago"""


class MercadoPagoService:
    """Wrapper HTTP para Mercado Pago Subscriptions/Preferences.

    Nota: Usamos HTTP para control explícito; se puede migrar al SDK oficial.
    """

    def __init__(self):
        base = "https://api.mercadopago.com"
        if getattr(settings, 'MERCADO_PAGO_SANDBOX', True):
            base = "https://api.sandbox.mercadopago.com"
        self.base_url = base
        self.access_token = settings.MERCADO_PAGO_ACCESS_TOKEN
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    def create_preference(self, email: str, plan_id: str, plan_amount: float, plan_frequency: str) -> dict:
        """Crea una preferencia de pago para iniciar suscripción recurrente."""
        freq_map = {
            'monthly': {'frequency': 1, 'frequency_type': 'months'},
            'yearly': {'frequency': 1, 'frequency_type': 'years'},
        }
        freq = freq_map.get(plan_frequency, freq_map['monthly'])

        payload = {
            "payer_email": email,
            "auto_recurring": {
                "frequency": freq['frequency'],
                "frequency_type": freq['frequency_type'],
                "transaction_amount": float(plan_amount),
                "currency_id": "UYU",
            },
            "back_urls": {
                "success": settings.MERCADO_PAGO_SUCCESS_URL,
                "failure": settings.MERCADO_PAGO_FAILURE_URL,
                "pending": settings.MERCADO_PAGO_PENDING_URL,
            },
            "notification_url": settings.MERCADO_PAGO_WEBHOOK_URL,
        }

        url = f"{self.base_url}/checkout/preferences"
        try:
            resp = requests.post(url, json=payload, headers=self.headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            logger.info(f"MP Preference created: {data.get('id')}")
            return data
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to create MP preference: {e}")
            raise MPException(str(e))

    def get_subscription(self, subscription_id: str) -> dict:
        url = f"{self.base_url}/v1/subscriptions/{subscription_id}"
        try:
            resp = requests.get(url, headers=self.headers, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get subscription {subscription_id}: {e}")
            raise MPException(str(e))

    def cancel_subscription(self, subscription_id: str) -> dict:
        url = f"{self.base_url}/v1/subscriptions/{subscription_id}"
        payload = {"status": "cancelled"}
        try:
            resp = requests.put(url, json=payload, headers=self.headers, timeout=10)
            resp.raise_for_status()
            logger.info(f"Subscription {subscription_id} cancelled in MP")
            return resp.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to cancel subscription {subscription_id}: {e}")
            raise MPException(str(e))

    def list_subscription_payments(self, subscription_id: str, limit: int = 100) -> list:
        url = f"{self.base_url}/v1/subscriptions/{subscription_id}/payments"
        params = {'limit': limit}
        try:
            resp = requests.get(url, params=params, headers=self.headers, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to list payments for {subscription_id}: {e}")
            raise MPException(str(e))
