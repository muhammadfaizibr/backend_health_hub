from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Profile
from apps.base.models import User


@receiver(post_save, sender=User)
def create_doctor_profile(sender, instance, created, **kwargs):
    """Automatically create doctor profile when a doctor user is created."""
    if created and instance.role == 'Doctor':
        Profile.objects.get_or_create(user=instance)