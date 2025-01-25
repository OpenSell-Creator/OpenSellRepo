from django.urls import path, include
from . import views

app_name = 'notifications'
urlpatterns = [
    path('notifications/', views.NotificationListView.as_view(), name='list'),
    path('mark-read/<int:notification_id>/', views.mark_notification_read, name='mark_read'),
    path('preferences/', views.notification_preferences, name='preferences'),
    ]