import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from avuweb.main.models import Subscription, SubscriptionEvent, UserProfile
from avuweb.main.services import MercadoPagoService, MPException


logger = logging.getLogger(__name__)
mp_service = MercadoPagoService()


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_subscription_event(self, event_id: int):
    """Procesa evento de webhook de Mercado Pago (async)."""
    try:
        event = SubscriptionEvent.objects.get(id=event_id)
        subscription = event.subscription
        payload = event.payload
        event_type = event.event_type

        logger.info(f"Processing event {event_type} for subscription {subscription.id}")

        if 'subscription' in event_type:
            _handle_subscription_event(subscription, payload)
        elif 'payment' in event_type:
            _handle_payment_event(subscription, payload)

        event.processed = True
        event.processed_at = timezone.now()
        event.save()
    except SubscriptionEvent.DoesNotExist:
        logger.error(f"Event {event_id} not found")
    except MPException as e:
        logger.warning(f"MP error processing event {event_id}: {e}")
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))
    except Exception as e:
        logger.exception(f"Error processing event {event_id}: {e}")
        try:
            event = SubscriptionEvent.objects.get(id=event_id)
            event.error_message = str(e)
            event.save()
        except Exception:
            pass
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))


def _handle_subscription_event(subscription: Subscription, payload: dict):
    status = payload.get('status')
    logger.info(f"Handling subscription event: status={status}")

    if status == 'authorized':
        subscription.status = 'active'
        subscription.preapproval_id = payload.get('id')
        _enable_user_profile(subscription.user_id)
    elif status == 'paused':
        subscription.status = 'paused'
    elif status == 'cancelled':
        subscription.status = 'cancelled'
        subscription.next_payment_date = None
        _disable_user_profile(subscription.user_id)
    elif status == 'pending':
        subscription.status = 'pending'

    subscription.mercado_pago_updated_at = timezone.now()
    subscription.save()


def _handle_payment_event(subscription: Subscription, payload: dict):
    status = payload.get('status')
    logger.info(f"Handling payment event: status={status}")

    if status == 'approved':
        subscription.last_payment_date = timezone.now()
        subscription.failed_payment_count = 0
        days = 365 if subscription.payment_frequency == 'yearly' else 30
        subscription.next_payment_date = timezone.now() + timedelta(days=days)
        _enable_user_profile(subscription.user_id)
    elif status == 'rejected':
        subscription.failed_payment_count += 1
        if subscription.failed_payment_count >= 4:
            subscription.status = 'failed'
            _disable_user_profile(subscription.user_id)
        else:
            subscription.status = 'paused'
    elif status == 'authorized':
        days = 365 if subscription.payment_frequency == 'yearly' else 30
        subscription.next_payment_date = timezone.now() + timedelta(days=days)

    subscription.mercado_pago_updated_at = timezone.now()
    subscription.save()


def _enable_user_profile(user_id: int):
    try:
        profile = UserProfile.objects.get(user_id=user_id)
        profile.enable_profile()
        logger.info(f"Profile enabled for user {user_id}")
    except UserProfile.DoesNotExist:
        logger.error(f"UserProfile not found for user {user_id}")


def _disable_user_profile(user_id: int):
    try:
        profile = UserProfile.objects.get(user_id=user_id)
        profile.disable_profile()
        logger.info(f"Profile disabled for user {user_id}")
    except UserProfile.DoesNotExist:
        logger.error(f"UserProfile not found for user {user_id}")


@shared_task
def sync_subscriptions_reconciliation():
    logger.info("Starting subscription reconciliation")
    cutoff = timezone.now() - timedelta(hours=6)
    stale = Subscription.objects.filter(last_synced_at__lt=cutoff, status__in=['active', 'pending'])

    for sub in stale:
        try:
            mp_data = mp_service.get_subscription(sub.mercado_pago_subscription_id)
            mp_status = mp_data.get('status')
            if mp_status != sub.status:
                sub.status = mp_status
                sub.mercado_pago_updated_at = timezone.now()
                if mp_status == 'active':
                    _enable_user_profile(sub.user_id)
                else:
                    _disable_user_profile(sub.user_id)
            sub.save()
        except Exception as e:
            logger.warning(f"Failed to sync subscription {sub.id}: {e}")


@shared_task
def check_pending_payment_dates():
    logger.info("Checking pending payment dates")
    tomorrow = timezone.now() + timedelta(days=1)
    upcoming = Subscription.objects.filter(
        next_payment_date__gte=timezone.now(),
        next_payment_date__lte=tomorrow,
        status='active'
    )
    for sub in upcoming:
        logger.info(f"Payment due soon for subscription {sub.id}")
