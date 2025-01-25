# messages/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('send/<uuid:product_id>/', views.send_message, name='send_message'),
    path('inbox/', views.inbox, name='inbox'),
    path('conversation/<int:conversation_id>/', views.conversation_detail, name='conversation_detail'),
]