# apps/patients/management/commands/process_earnings.py

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction


class Command(BaseCommand):
    help = 'Process pending earnings immediately and move them to available balance'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be processed without making changes',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed output',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        verbose = options['verbose']
        
        self.stdout.write(self.style.WARNING('=' * 60))
        self.stdout.write(self.style.WARNING('Processing Pending Earnings (IMMEDIATE)'))
        self.stdout.write(self.style.WARNING('=' * 60))
        
        from apps.payments.models import WalletLedger
        from apps.base.models import Wallet
        
        # Get ALL pending entries (no date check)
        pending_entries = WalletLedger.objects.filter(
            status='pending'
        ).select_related('wallet', 'wallet__user')
        
        count = pending_entries.count()
        
        if count == 0:
            self.stdout.write(self.style.SUCCESS('\nNo pending earnings to process'))
            return
        
        if dry_run:
            self.stdout.write(self.style.NOTICE('\n[DRY RUN MODE] No changes will be made\n'))
            self.stdout.write(f'Found {count} pending entries to process:\n')
            
            if verbose:
                total_amount = 0
                for entry in pending_entries:
                    total_amount += entry.amount
                    self.stdout.write(
                        f'  - Ledger ID: {entry.id} | '
                        f'User: {entry.wallet.user.get_full_name()} | '
                        f'Amount: ${entry.amount} | '
                        f'Created: {entry.created_at} | '
                        f'Available at: {entry.available_at}'
                    )
                self.stdout.write(f'\nTotal amount to process: ${total_amount}')
        else:
            self.stdout.write(f'\nProcessing {count} pending entries...\n')
            
            updated_count = 0
            failed_count = 0
            total_amount = 0
            
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
                        total_amount += entry.amount
                        
                        if verbose:
                            self.stdout.write(
                                f'  ✓ Processed: {entry.wallet.user.get_full_name()} - ${entry.amount}'
                            )
                            
                except Exception as e:
                    failed_count += 1
                    self.stdout.write(
                        self.style.ERROR(f'  ✗ Error processing ledger entry {entry.id}: {str(e)}')
                    )
                    continue
            
            self.stdout.write(self.style.SUCCESS(f'\n✓ Successfully processed: {updated_count} entries'))
            self.stdout.write(self.style.SUCCESS(f'✓ Total amount processed: ${total_amount}'))
            
            if failed_count > 0:
                self.stdout.write(self.style.ERROR(f'✗ Failed: {failed_count} entries'))
        
        self.stdout.write(self.style.WARNING('\n' + '=' * 60))