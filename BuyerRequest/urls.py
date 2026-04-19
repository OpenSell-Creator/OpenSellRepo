from django.urls import path
from django.shortcuts import render, get_object_or_404, redirect
from . import views

app_name = 'buyer_requests'

urlpatterns = [
    # Main request views
    path('requests/', views.BuyerRequestListView.as_view(), name='list'),
    path('requests/categories/', views.request_categories, name='categories'),
    path('requests/create/', views.BuyerRequestCreateView.as_view(), name='create'),
    path('requests/<uuid:pk>/', views.BuyerRequestDetailView.as_view(), name='detail'),
    path('requests/<uuid:pk>/edit/', views.BuyerRequestUpdateView.as_view(), name='update'),
    path('requests/<uuid:pk>/delete/', views.BuyerRequestDeleteView.as_view(), name='delete'),
    
    # Request actions
    path('<uuid:request_id>/bump/', views.bump_request, name='bump_request'),
    path('<uuid:request_id>/respond/', views.create_response, name='create_response'),
    path('report/<uuid:request_id>/',lambda request, request_id: redirect('report_item', 'request', request_id),name='report_request'),
    
    path('response/<uuid:response_id>/status/', views.update_response_status, name='update_response_status'),
    
    # AJAX endpoints 
    path('ajax/subcategories/', views.load_subcategories, name='ajax_subcategories'),
    path('ajax/brands/', views.load_brands, name='ajax_brands'),
    path('ajax/lgas/', views.load_lgas, name='ajax_lgas'),
]