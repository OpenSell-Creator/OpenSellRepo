from django.urls import path, include
from . import views
from .views import NotificationListView, NotificationDetailView

app_name = 'notifications'
urlpatterns = [
    # Main notification views
    path('notifications/', views.NotificationListView.as_view(), name='list'),
    path('detail/<int:pk>/', views.NotificationDetailView.as_view(), name='detail'),
    path('preferences/', views.notification_preferences, name='preferences'),
    
    # AJAX endpoints
    path('api/', views.NotificationAPIView.as_view(), name='api'),
    path('mark-read/<int:notification_id>/', views.mark_notification_read, name='mark_read'),
    path('mark-all-read/', views.mark_all_read, name='mark_all_read'),
    path('clear-all/', views.clear_all_notifications, name='clear_all'),
    path('delete/<int:notification_id>/', views.delete_notification, name='delete'),
    path('stats/', views.notification_stats, name='stats'),
    
    # Push notification endpoints (optional)
    path('subscribe-push/', views.subscribe_push, name='subscribe_push'),
    path('unsubscribe-push/', views.unsubscribe_push, name='unsubscribe_push'),
    
    # Admin endpoints (optional)
    path('bulk-send/', views.send_bulk_notification, name='bulk_send'),
]