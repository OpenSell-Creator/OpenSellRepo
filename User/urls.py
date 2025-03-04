from django.contrib import admin
from django.urls import path,include
from . import views
from .views import ProfileUpdateView

urlpatterns = [
    path('login/', views.loginview, name='login'),
    path('logout/', views.logoutview, name='logout'),
    path('register/', views.register_user, name='register'),
    path('profile-menu/', views.profile_menu, name='profile_menu'),
    path('profile/update/', ProfileUpdateView.as_view(), name='profile_update'),
    
    path('api/lgas/<int:state_id>/', views.load_lgas, name='load_lgas'),

]