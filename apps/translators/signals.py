from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.core.exceptions import ValidationError

from .models import Profile, TranslatorReview


@receiver(post_save, sender=Profile)
def validate_translator_role(sender, instance, created, **kwargs):
    """Ensure only users with Translator role can have a translator profile."""
    if created and hasattr(instance.user, 'role') and instance.user.role != 'Translator':
        instance.delete()
        raise ValidationError("Only users with Translator role can have a translator profile.")


@receiver(post_save, sender=TranslatorReview)
def notify_translator_new_review(sender, instance, created, **kwargs):
    """Send notification to translator when they receive a new review."""
    if created and instance.status == 'Published':
        # TODO: Implement notification system
        # send_notification(
        #     user=instance.translator.user,
        #     message=f"You received a new {instance.rating}-star review from {instance.patient.user.get_full_name()}"
        # )
        pass


@receiver(pre_delete, sender=Profile)
def cleanup_translator_data(sender, instance, **kwargs):
    """Clean up related data when translator profile is deleted."""
    # Soft delete reviews instead of hard delete
    instance.reviews.update(status='Hidden')