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
        email_template_name='password_reset_email.txt',  # Plain text version
        html_email_template_name='password_reset_email.html',  # Add this line
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
    
    path('api/lgas/<int:state_id>/', views.load_lgas, name='load_lgas'),
]