import hashlib
import hmac
import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.conf import settings

from avuweb.main.models import Subscription, SubscriptionEvent
from avuweb.main.tasks import process_subscription_event


logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["POST"])
def mercado_pago_webhook(request):
    """Maneja webhooks de Mercado Pago: valida firma, persiste y encola evento."""
    try:
        signature = request.headers.get('X-Signature', '')
        request_id = request.headers.get('X-Request-Id', '')

        if not signature or not request_id:
            logger.warning("Missing signature or request ID in webhook")
            return JsonResponse({'error': 'Missing headers'}, status=400)

        if not _validate_webhook_signature(request.body, signature, request_id):
            logger.warning(f"Invalid webhook signature: {request_id}")
            return JsonResponse({'error': 'Invalid signature'}, status=401)

        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError:
            logger.error("Invalid JSON in webhook")
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        event_id = payload.get('id')
        event_type = payload.get('type')
        resource_id = payload.get('data', {}).get('id')

        if not event_id or not event_type or not resource_id:
            logger.error(f"Missing required fields in webhook: {request_id}")
            return JsonResponse({'error': 'Missing required fields'}, status=400)

        if 'subscription' not in event_type and 'payment' not in event_type:
            logger.info(f"Ignoring event type: {event_type}")
            return JsonResponse({'status': 'ignored'}, status=200)

        # Buscar suscripción por ID o preapproval
        subscription = None
        try:
            subscription = Subscription.objects.get(mercado_pago_subscription_id=resource_id)
        except Subscription.DoesNotExist:
            try:
                subscription = Subscription.objects.get(preapproval_id=resource_id)
            except Subscription.DoesNotExist:
                logger.warning(f"Subscription not found for resource: {resource_id}")
                return JsonResponse({'error': 'Subscription not found'}, status=404)

        event, created = SubscriptionEvent.objects.get_or_create(
            mercado_pago_event_id=event_id,
            defaults={
                'subscription': subscription,
                'event_type': event_type,
                'payload': payload,
            }
        )

        if not created:
            logger.info(f"Duplicate webhook received: {event_id}")
            return JsonResponse({'status': 'already_processed'}, status=200)

        # Encola procesamiento async
        process_subscription_event.delay(event.id)
        logger.info(f"Webhook received and queued: {event_id}")
        return JsonResponse({'status': 'received'}, status=200)

    except Exception as e:
        logger.exception(f"Webhook handler error: {e}")
        return JsonResponse({'error': 'Internal server error'}, status=500)


def _validate_webhook_signature(body: bytes, signature: str, request_id: str) -> bool:
    """Valida la firma HMAC-SHA256 de Mercado Pago."""
    try:
        parts = {}
        for part in signature.split(','):
            if '=' in part:
                key, value = part.split('=', 1)
                parts[key] = value

        timestamp = parts.get('ts')
        received_hash = parts.get('v1')
        if not timestamp or not received_hash:
            logger.warning("Invalid signature format")
            return False

        body_str = body.decode('utf-8') if isinstance(body, bytes) else str(body)
        signing_string = f"{request_id}.{timestamp}.{body_str}"

        secret = getattr(settings, 'MERCADO_PAGO_WEBHOOK_SECRET', '').encode()
        calculated_hash = hashlib.sha256(signing_string.encode('utf-8')).hexdigest()

        return hmac.compare_digest(calculated_hash, received_hash)
    except Exception as e:
        logger.error(f"Signature validation error: {e}")
        return False
