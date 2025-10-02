from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import User, Wallet


@receiver(post_save, sender=User)
def create_user_wallet(sender, instance, created, **kwargs):
    """Automatically create a wallet when a new user is created."""
    if created and not hasattr(instance, 'wallet'):
        Wallet.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_wallet(sender, instance, **kwargs):
    """Ensure wallet is saved when user is saved."""
    if hasattr(instance, 'wallet'):
        instance.wallet.save()