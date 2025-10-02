from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
import re
from rest_framework.serializers import ValidationError

phone_regex = RegexValidator(
    regex=r'^\+?1?\d{9,15}$',
    message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
)


def validate_unique_email(value):
    from apps.base.models import User
    if User.objects.filter(email=value).exists():
        raise ValidationError("Email already exists.")


def validate_unique_phone(value):
    from apps.base.models import User
    if User.objects.filter(phone_number=value).exists():
        raise ValidationError("Phone number already exists.")


def validate_date_range(start_date, end_date):
    if start_date and end_date and start_date > end_date:
        raise ValidationError("Start date cannot be after end date.")