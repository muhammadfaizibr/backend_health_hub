from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver
from django.core.files.storage import default_storage
from .models import File
import logging

logger = logging.getLogger(__name__)


@receiver(post_delete, sender=File)
def delete_file_from_storage(sender, instance, **kwargs):
    """
    Delete file from storage when File model instance is deleted.
    This ensures orphaned files don't remain in storage.
    """
    if instance.file_path:
        try:
            if default_storage.exists(instance.file_path):
                default_storage.delete(instance.file_path)
                logger.info(f"Deleted file from storage: {instance.file_path}")
        except Exception as e:
            logger.error(f"Failed to delete file {instance.file_path}: {str(e)}")


@receiver(pre_save, sender=File)
def delete_old_file_on_path_change(sender, instance, **kwargs):
    """
    Delete old file from storage if file_path is changed.
    This prevents orphaned files when updating file location.
    """
    if not instance.pk:
        return

    try:
        old_file = File.objects.get(pk=instance.pk)
        if old_file.file_path != instance.file_path:
            if default_storage.exists(old_file.file_path):
                default_storage.delete(old_file.file_path)
                logger.info(f"Deleted old file from storage: {old_file.file_path}")
    except File.DoesNotExist:
        pass
    except Exception as e:
        logger.error(f"Error in pre_save signal: {str(e)}")