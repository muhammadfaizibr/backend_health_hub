from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.html import strip_tags


def send_welcome_email(user):
    """Send welcome email to new user."""
    subject = 'Welcome to Health Hub!'
    html_message = render_to_string('emails/welcome_email.html', {'user': user})
    plain_message = strip_tags(html_message)
    send_mail(
        subject,
        plain_message,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        html_message=html_message,
    )


def send_appointment_confirmation(appointment, patient, doctor):
    """Send appointment confirmation email."""
    subject = f'Appointment Confirmed with Dr. {doctor.first_name}'
    html_message = render_to_string(
        'emails/appointment_confirmation.html',
        {'appointment': appointment, 'patient': patient, 'doctor': doctor}
    )
    plain_message = strip_tags(html_message)
    send_mail(
        subject,
        plain_message,
        settings.DEFAULT_FROM_EMAIL,
        [patient.user.email],
        html_message=html_message,
    )