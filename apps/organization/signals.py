from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from decimal import Decimal
from .models import PackagePurchase, CreditsLedger, Profile


@receiver(pre_save, sender=Profile)
def validate_credits_balance(sender, instance, **kwargs):
    """Ensure credits balance doesn't go negative."""
    if instance.current_credits_balance < 0:
        raise ValueError("Credits balance cannot be negative.")


@receiver(post_save, sender=PackagePurchase)
def handle_purchase_status_change(sender, instance, created, **kwargs):
    """
    Handle purchase completion and credit allocation.
    This is a backup - main logic should be in serializer.
    """
    if not created:
        # Status changed - might need to handle completion
        pass


@receiver(post_save, sender=CreditsLedger)
def log_ledger_entry(sender, instance, created, **kwargs):
    """Log ledger entries for auditing purposes."""
    if created:
        # Could integrate with logging system or notifications
        pass