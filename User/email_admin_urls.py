"""
Replaces the email lines in User/urls.py. Remove these from User/urls.py:
    bulk_email_list, bulk_email_create, bulk_email_detail, quick_announcement, email_template_library,
    bulk_email_send_now, email_preference_dashboard, create_missing_preferences, preview_recipients
and add this ABOVE the remaining paths:
    path('admin/', include('User.email_admin_urls')),
Every url name is unchanged, so existing links keep working. Five are new: edit, delete, duplicate, send_batch, retry_failed.
"""
from django.urls import path

from . import email_admin_views as v

urlpatterns = [
    path('bulk-emails/', v.bulk_email_list, name='bulk_email_list'),
    path('bulk-emails/create/', v.bulk_email_create, name='bulk_email_create'),
    path('bulk-emails/<int:pk>/', v.bulk_email_detail, name='bulk_email_detail'),
    path('bulk-emails/<int:pk>/edit/', v.bulk_email_edit, name='bulk_email_edit'),
    path('bulk-emails/<int:pk>/delete/', v.bulk_email_delete, name='bulk_email_delete'),
    path('bulk-emails/<int:pk>/duplicate/', v.bulk_email_duplicate, name='bulk_email_duplicate'),
    path('bulk-emails/<int:pk>/send-now/', v.bulk_email_send_now, name='bulk_email_send_now'),
    path('bulk-emails/send-batch/', v.bulk_email_send_batch, name='bulk_email_send_batch'),
    path('bulk-emails/<int:pk>/retry-failed/', v.bulk_email_retry_failed, name='bulk_email_retry_failed'),
    path('quick-announcement/', v.quick_announcement, name='quick_announcement'),
    path('email-templates/', v.email_template_library, name='email_template_library'),
    path('email-preferences/dashboard/', v.email_preference_dashboard, name='email_preference_dashboard'),
    path('email-preferences/create-missing/', v.create_missing_preferences, name='create_missing_preferences'),
    path('email-preferences/preview/', v.preview_recipients, name='preview_recipients'),
]
