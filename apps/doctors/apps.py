from django.apps import AppConfig


class DoctorsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.doctors'
    verbose_name = 'Doctor Management'

    def ready(self):
        import apps.doctors.signals