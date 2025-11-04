# apps/patients/management/commands/update_appointments.py

from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.patients.tasks import update_appointment_statuses


class Command(BaseCommand):
    help = 'Check and update appointment statuses based on current time'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without making changes',
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
        self.stdout.write(self.style.WARNING('Updating Appointment Statuses'))
        self.stdout.write(self.style.WARNING('=' * 60))
        
        if dry_run:
            self.stdout.write(self.style.NOTICE('\n[DRY RUN MODE] No changes will be made\n'))
            
            # Show what would be updated
            from apps.patients.models import Appointment
            now = timezone.now()
            
            appointments = Appointment.objects.filter(
                status__in=['confirmed', 'in_progress']
            ).select_related('time_slot', 'case__doctor', 'translator')
            
            count = appointments.count()
            
            if count == 0:
                self.stdout.write(self.style.SUCCESS('No appointments need status updates'))
            else:
                self.stdout.write(f'Found {count} appointments to check:\n')
                
                if verbose:
                    for apt in appointments:
                        slot_time = f"{apt.time_slot.start_time} - {apt.time_slot.end_time}" if apt.time_slot else "N/A"
                        self.stdout.write(
                            f'  - Appointment ID: {apt.id} | '
                            f'Current Status: {apt.status} | '
                            f'Time Slot: {slot_time} | '
                            f'Doctor: {apt.case.doctor.get_full_name()}'
                        )
        else:
            self.stdout.write('Starting processing...\n')
            
            try:
                result = update_appointment_statuses()
                self.stdout.write(self.style.SUCCESS(f'\n✓ {result}'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'\n✗ Error: {str(e)}'))
                raise
        
        self.stdout.write(self.style.WARNING('\n' + '=' * 60))