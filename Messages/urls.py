# Messages/urls.py
from django.urls import path
from . import views

urlpatterns = [

    path('inbox/', views.inbox, name='inbox'),
    path('detail/<uuid:conversation_uuid>/', views.conversation_detail, name='conversation_detail'),
    
    # Product
    path('send/<uuid:product_id>/', views.send_message, name='send_message'),

    # Service
    path('send/service/<uuid:service_id>/', views.send_service_message, name='send_service_message'),

    # Buyer Request
    path('send/request/<uuid:request_id>/', views.send_request_message, name='send_request_message'),
]