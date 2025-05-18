from django.urls import path
from . import views

urlpatterns = [
    path('about/', views.about, name='about'),
    path('contact/', views.contact, name='contact'),
    path('faq/', views.faq, name='faq'),
    path('terms/', views.terms, name='terms'),
    path('privacy/', views.privacy, name='privacy'),
    path('cookies/', views.cookie_policy, name='cookies'),
    path('api/cookie-consent/', views.save_cookie_consent, name='save_cookie_consent'),
    path('support/', views.support, name='support'),
    path('safety/', views.safety, name='safety'),
]