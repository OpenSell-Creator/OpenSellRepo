"""
URL configuration for OpenSell project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.contrib import admin
from django.urls import path, include
from django.contrib.sitemaps.views import sitemap
from django.conf.urls.static import static
from .robots import robots_txt
from .sitemaps import StaticViewSitemap, ProductSitemap, CategorySitemap, SubcategorySitemap

handler404 = 'Home.views.handler404'
sitemaps = {
    'static': StaticViewSitemap,
    'products': ProductSitemap,
    'categories': CategorySitemap,
    'subcategories': SubcategorySitemap,
}

urlpatterns = [
    path('controlroom/', admin.site.urls),
    path('', include('Home.urls')),
    path('', include('User.urls')),
    path('', include('Messages.urls')),
    path('', include('Notifications.urls')),
    path('', include('Dashboard.urls')),
    path('', include('Pages.urls')),
    path('accounts/', include('allauth.urls')),
    path('robots.txt', robots_txt),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps},
         name='django.contrib.sitemaps.views.sitemap'),
    
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, 
                          document_root=settings.MEDIA_ROOT)
