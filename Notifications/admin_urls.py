"""
Include from the project urls.py, above the 'controlroom/' admin route:
    path('controlroom/notify/', include('Notifications.admin_urls')),
Names are all prefixed notif_admin_ so they cannot clash with the app's own 'notifications:' names.
"""
from django.urls import path

from . import admin_views as v

urlpatterns = [
    path('', v.compose, name='notif_admin_compose'),
    path('withdraw/<int:pk>/', v.withdraw, name='notif_admin_withdraw'),
    path('browse/', v.notification_list, name='notif_admin_list'),
    path('browse/<int:pk>/delete/', v.notification_delete, name='notif_admin_delete'),
    path('overview/', v.overview, name='notif_admin_overview'),
    path('overview/cleanup/', v.cleanup, name='notif_admin_cleanup'),
    path('overview/test-push/', v.test_push, name='notif_admin_test_push'),
]
