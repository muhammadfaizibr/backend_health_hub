# apps/patients/tasks.py

from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from .models import Appointment


@shared_task
def update_appointment_statuses():
    """
    Periodic task to check and update appointment statuses.
    Run this every 5 minutes via Celery Beat.
    """
    now = timezone.now()
    
    # Get appointments that might need status updates
    appointments = Appointment.objects.filter(
        status__in=['confirmed', 'in_progress']
    ).select_related('time_slot', 'case__doctor', 'translator')
    
    updated_count = 0
    for appointment in appointments:
        old_status = appointment.status
        appointment.check_and_update_status()
        
        if old_status != appointment.status:
            updated_count += 1
    
    return f'Updated {updated_count} appointment statuses'


@shared_task
def process_pending_earnings():
    """
    Move pending earnings to available after 3 days.
    Run this daily via Celery Beat.
    """
    from apps.payments.models import WalletLedger
    from apps.base.models import Wallet
    from django.db import transaction
    
    now = timezone.now()
    
    # Get pending entries that should become available
    pending_entries = WalletLedger.objects.filter(
        status='pending',
        available_at__lte=now
    ).select_related('wallet')
    
    updated_count = 0
    
    for entry in pending_entries:
        try:
            with transaction.atomic():
                wallet = Wallet.objects.select_for_update().get(pk=entry.wallet.pk)
                
                # Move from pending to available
                wallet.pending_balance -= entry.amount
                wallet.available_balance += entry.amount
                wallet.save()
                
                entry.status = 'available'
                entry.balance_type = 'available'
                entry.save()
                
                updated_count += 1
        except Exception as e:
            # Log error but continue processing
            print(f"Error processing ledger entry {entry.id}: {str(e)}")
            continue
    
    return f'Processed {updated_count} pending earnings'