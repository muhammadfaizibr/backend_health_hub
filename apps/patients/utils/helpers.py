from datetime import timedelta
from django.utils import timezone


def validate_appointment_slot(slot, duration):
    """Validate if the slot has enough time."""
    slot_end = slot.start_time + timedelta(minutes=slot.duration)
    if slot_end > slot.end_time:  # Assuming end_time in slot
        raise ValueError("Insufficient slot duration.")
    return True


def generate_appointment_number(case):
    """Generate next appointment number for case."""
    return case.appointments.count() + 1