from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/not_live/', views.dashboard_home, name='dashboard_home'),
    path('transactions/', views.transaction_history, name='transaction_history'),
    path('deposit/', views.deposit_funds, name='deposit_funds'),
    path('boost/<uuid:product_id>/', views.boost_product, name='boost_product'),
    path('subscription/', views.subscription_management, name='subscription_management'),
    path('account/status/', views.account_status, name='account_status'),
    path('boost/status/', views.product_boost_status, name='product_boost_status'),
    path('api/transaction/<int:transaction_id>/', views.get_transaction_details, name='transaction_details_api'),
    path('api/stats/', views.dashboard_stats_api, name='dashboard_stats_api'),
    path('admin/tasks/', views.task_monitor, name='task_monitor'),
]