from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.dashboard_home, name='dashboard_home'),
    path('transactions/', views.transaction_history, name='transaction_history'),
    path('deposit/', views.deposit_funds, name='deposit_funds'),
    path('boost/<uuid:product_id>/', views.boost_product, name='boost_product'),
    path('status/', views.account_status, name='account_status'),
]