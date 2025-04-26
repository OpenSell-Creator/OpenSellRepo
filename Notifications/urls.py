from django.urls import path, include
from . import views
from .views import NotificationListView, NotificationDetailView, MarkNotificationAsReadView

app_name = 'notifications'
urlpatterns = [
    path('notifications/', views.NotificationListView.as_view(), name='list'),
    path('mark-read/<int:notification_id>/', views.mark_notification_read, name='mark_read'),
    path('preferences/', views.notification_preferences, name='preferences'),
    path('notification/<int:pk>/', NotificationDetailView.as_view(), name='detail'),
    path('mark-read/<int:pk>/', MarkNotificationAsReadView.as_view(), name='mark_read'),
    path('mark-all-read/', views.mark_all_read, name='mark_all_read'),
    path('clear-all/', views.clear_all_notifications, name='clear_all'),
    ]