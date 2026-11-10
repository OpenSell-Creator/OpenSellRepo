"""
Include from the project urls.py, above the 'controlroom/' admin route:
    path('controlroom/services/', include('Services.admin_urls')),
Names are all prefixed svc_admin_ so they cannot clash with the app's own 'services:' names.
"""
from django.urls import path

from . import admin_views as v

urlpatterns = [
    path('', v.listing_list, name='svc_admin_list'),
    path('<uuid:pk>/', v.listing_detail, name='svc_admin_detail'),
    path('<uuid:pk>/suspend/', v.listing_suspend, name='svc_admin_suspend'),
    path('<uuid:pk>/unsuspend/', v.listing_unsuspend, name='svc_admin_unsuspend'),
    path('<uuid:pk>/feature/', v.listing_feature, name='svc_admin_feature'),
    path('<uuid:pk>/activate/', v.listing_activate, name='svc_admin_activate'),
    path('<uuid:pk>/delete/', v.listing_delete, name='svc_admin_delete'),
    path('inquiries/', v.inquiry_list, name='svc_admin_inquiries'),
    path('inquiries/<uuid:pk>/cancel/', v.inquiry_cancel, name='svc_admin_inquiry_cancel'),
    path('reviews/', v.review_list, name='svc_admin_reviews'),
    path('reviews/<int:pk>/delete/', v.review_delete, name='svc_admin_review_delete'),
    path('replies/<int:pk>/delete/', v.reply_delete, name='svc_admin_reply_delete'),
    path('overview/', v.overview, name='svc_admin_overview'),
    path('overview/run/<slug:action>/', v.tool_run, name='svc_admin_tool'),
]
