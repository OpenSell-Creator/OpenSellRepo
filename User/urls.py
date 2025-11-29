from django.contrib import admin
from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from .views import ProfileUpdateView

urlpatterns = [
    path('login/', views.loginview, name='login'),
    path('logout/', views.logoutview, name='logout'),
    path('signup/', views.signup_options, name='signup'),
    path('register/', views.register_user, name='register'),
    
    path('password-reset/',
    auth_views.PasswordResetView.as_view(
        template_name='password_reset.html',
        email_template_name='password_reset_email.txt',
        html_email_template_name='password_reset_email.html',
        from_email='OpenSell <no-reply@opensell.online>',
        subject_template_name='password_reset_subject.txt'
    ),
    name='password_reset'),
    
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(
            template_name='password_reset_done.html'
        ),  name='password_reset_done'),
    
    path('password-reset-confirm/<uidb64>/<token>/', 
        auth_views.PasswordResetConfirmView.as_view(
            template_name='password_reset_confirm.html'
        ), 
        name='password_reset_confirm'),
    
    path('password-reset-complete/', 
        auth_views.PasswordResetCompleteView.as_view(
            template_name='password_reset_complete.html'
        ), 
        name='password_reset_complete'),
    
    path('email-preferences/', views.email_preferences, name='email_preferences'),
    path('unsubscribe/', views.unsubscribe_all, name='unsubscribe_all'),
    
    path('profile-menu/', views.profile_menu, name='profile_menu'),
    path('profile/update/', ProfileUpdateView.as_view(), name='profile_update'),
    
    path('send-verification-otp/', views.send_verification_otp, name='send_verification_otp'),
    path('verify-email/', views.verify_email_form, name='verify_email_form'),
    
    path('business/status/', views.business_verification_status, name='business_verification_status'),
    path('business/upload-document/', views.upload_business_document, name='upload_business_document'),
    path('business/verify/', views.business_verification_form, name='business_verification_form'),
    
    # Admin URLs
    path('admin-panel/', views.admin_panel, name='admin_panel'),
    path('admin/business-verifications/', views.admin_business_verifications, name='admin_business_verifications'),
    path('admin/verify-business/<int:profile_id>/', views.admin_verify_business, name='admin_verify_business'),
    
    path('admin/bulk-emails/', views.bulk_email_list, name='bulk_email_list'),
    path('admin/bulk-emails/create/', views.bulk_email_create, name='bulk_email_create'),
    path('admin/bulk-emails/<int:pk>/', views.bulk_email_detail, name='bulk_email_detail'),
    path('admin/quick-announcement/', views.quick_announcement, name='quick_announcement'),
    path('admin/bulk-emails/<int:pk>/send-now/', views.bulk_email_send_now, name='bulk_email_send_now'),
    
    path('admin/email-preferences/dashboard/', views.email_preference_dashboard, name='email_preference_dashboard'),
    path('admin/email-preferences/create-missing/', views.create_missing_preferences, name='create_missing_preferences'),
    path('admin/email-preferences/preview/', views.preview_recipients, name='preview_recipients'),
    
    # API endpoints
    path('api/lgas/<int:state_id>/', views.load_lgas, name='load_lgas'),
]