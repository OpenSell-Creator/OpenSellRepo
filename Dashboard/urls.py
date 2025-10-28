from django.urls import path
from . import views
from .monnify_webhook import monnify_webhook

urlpatterns = [
    path('dashboard/', views.dashboard_home, name='dashboard_home'),
    path('deposit/', views.deposit_funds_monnify, name='deposit_with_monnify'),
    path('transactions/', views.transaction_history, name='transaction_history'),
    path('boost/<uuid:product_id>/', views.boost_product, name='boost_product'),
    path('subscription/', views.subscription_management, name='subscription_management'),
    path('account/status/', views.account_status, name='account_status'),
    path('boost/status/', views.product_boost_status, name='product_boost_status'),
    
    
    path('api/transaction/<int:transaction_id>/', views.get_transaction_details, name='transaction_details_api'),
    path('api/stats/', views.dashboard_stats_api, name='dashboard_stats_api'),
    
    path('admin/tasks/', views.task_monitor, name='task_monitor'),
    
    path('api/create-permanent-account/', views.create_permanent_virtual_account, name='create_permanent_account'),
    path('api/generate-quick-transfer/', views.generate_reserved_account, name='generate_reserved_account'),
    path('api/check-payment-status/', views.check_payment_status, name='check_payment_status'),
    path('api/get-account-details/', views.get_virtual_account_info, name='get_account_details'),
    path('api/test/', views.test_json_response, name='test_json'),
    
    
    # Webhook (NO authentication required - must be publicly accessible)
    path('webhook/monnify/', monnify_webhook, name='monnify_webhook'),
    path('webhook/monnify', monnify_webhook, name='monnify_webhook_no_slash'),
]