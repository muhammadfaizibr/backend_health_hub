from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from .models import Transaction, Refund, AppointmentBilling, PayoutRequest


@receiver(post_save, sender=Transaction)
def update_transaction_completed_at(sender, instance, created, **kwargs):
    """Automatically set completed_at when transaction succeeds."""
    if not created and instance.status in ['Success', 'Failed'] and not instance.completed_at:
        Transaction.objects.filter(pk=instance.pk).update(completed_at=timezone.now())


@receiver(post_save, sender=Refund)
def update_transaction_on_refund(sender, instance, created, **kwargs):
    """Update transaction status when refund is processed."""
    if instance.status == 'Processed':
        transaction = instance.transaction
        total_refunded = transaction.refunded_amount
        
        if total_refunded >= transaction.amount:
            transaction.status = 'Refunded'
        else:
            transaction.status = 'Partially Refunded'
        transaction.save()


@receiver(pre_save, sender=AppointmentBilling)
def calculate_billing_total(sender, instance, **kwargs):
    """Auto-calculate total amount before saving."""
    instance.total_amount = instance.doctor_fee + instance.translator_fee + instance.platform_fee


@receiver(post_save, sender=PayoutRequest)
def create_payout_notification(sender, instance, created, **kwargs):
    """Send notification when payout status changes."""
    if not created and instance.status == 'Completed':
        # TODO: Implement notification system
        # send_notification(
        #     user=instance.wallet.user,
        #     message=f"Your payout of {instance.amount} {instance.currency} has been completed."
        # )
        pass