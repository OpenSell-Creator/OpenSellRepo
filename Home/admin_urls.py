"""
Include from the project urls.py:
    path('controlroom/home/', include('Home.admin_urls')),
Names are all prefixed home_admin_ so they cannot clash with existing routes.
"""
from django.urls import path

from . import admin_views as v

urlpatterns = [
    path('banners/', v.banner_list, name='home_admin_banners'),
    path('banners/new/', v.banner_form, name='home_admin_banner_new'),
    path('banners/<int:pk>/edit/', v.banner_form, name='home_admin_banner_edit'),
    path('banners/<int:pk>/toggle/', v.banner_toggle, name='home_admin_banner_toggle'),
    path('banners/<int:pk>/delete/', v.banner_delete, name='home_admin_banner_delete'),

    path('catalog/', v.catalog_list, name='home_admin_catalog'),
    path('catalog/<str:kind>/new/', v.catalog_form, name='home_admin_catalog_new'),
    path('catalog/<str:kind>/<int:pk>/edit/', v.catalog_form, name='home_admin_catalog_edit'),
    path('catalog/<str:kind>/<int:pk>/delete/', v.catalog_delete, name='home_admin_catalog_delete'),

    path('listings/', v.listing_list, name='home_admin_listings'),
    path('listings/<uuid:pk>/suspend/', v.listing_suspend, name='home_admin_listing_suspend'),
    path('listings/<uuid:pk>/unsuspend/', v.listing_unsuspend, name='home_admin_listing_unsuspend'),
    path('listings/<uuid:pk>/delete/', v.listing_delete, name='home_admin_listing_delete'),

    path('reviews/', v.review_list, name='home_admin_reviews'),
    path('reviews/<int:pk>/delete/', v.review_delete, name='home_admin_review_delete'),
    path('reviews/replies/<int:pk>/delete/', v.reply_delete, name='home_admin_reply_delete'),

    path('tools/', v.tools, name='home_admin_tools'),
    path('tools/run/<slug:action>/', v.tool_run, name='home_admin_tool_run'),
]
