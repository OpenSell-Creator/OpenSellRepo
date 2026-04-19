from django.urls import path
from . import views
from django.shortcuts import render, get_object_or_404, redirect

app_name = 'services'

urlpatterns = [
    # Main service views
    path('services/', views.ServiceListView.as_view(), name='list'),
    path('services/categories/', views.service_categories, name='categories'),
    path('services/create/', views.ServiceCreateView.as_view(), name='create'),

    # User's services 

    path('services/<uuid:pk>/', views.ServiceDetailView.as_view(), name='detail'),
    path('services/<uuid:pk>/edit/', views.ServiceUpdateView.as_view(), name='update'),
    path('services/<uuid:pk>/delete/', views.ServiceDeleteView.as_view(), name='delete'),
 
    # Service actions
    path('services/<uuid:service_id>/message/',lambda request, service_id: redirect('send_service_message', service_id=service_id),name='send_message'),
    path('services/<uuid:service_id>/inquire/', views.create_inquiry, name='create_inquiry'),
    path('services/<uuid:service_id>/review/', views.submit_service_review, name='submit_review'),
    path('report/<uuid:service_id>/', lambda request, service_id: redirect('report_item', 'service', service_id),name='report_service'),
    

    # AJAX endpoints 
    path('ajax/lgas/', views.load_lgas, name='ajax_lgas'),
    
    # Inquiry management (for providers)
    path('inquiries/', views.my_inquiries, name='my_inquiries'),
    path('inquiry/<uuid:pk>/', views.inquiry_detail, name='inquiry_detail'),
    path('inquiry/<uuid:pk>/respond/', views.respond_to_inquiry, name='respond_to_inquiry'),
    
]