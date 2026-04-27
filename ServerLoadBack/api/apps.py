from django.apps import AppConfig


class ApiConfig(AppConfig):
    name = 'api'

    def ready(self):
        from api.alert_worker import start_alert_worker_if_enabled

        start_alert_worker_if_enabled()
