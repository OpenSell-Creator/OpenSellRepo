from django.apps import AppConfig


class BuyerRequestConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'BuyerRequest'
    verbose_name = 'Buyer Requests'
    
    def ready(self):
        import BuyerRequest.signals