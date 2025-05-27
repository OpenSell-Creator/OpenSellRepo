from django.contrib import admin
from django.urls import path,include
from . import views
from .views import QuickUpdateView, ReportProductView, AllSellerReviewsView
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', views.home, name='home'),
    path('categories/', views.category_list, name='category_list'),
    path('product/<uuid:pk>/', views.ProductDetailView.as_view(), name='product_detail'),
    path('products/', views.ProductListView.as_view(), name='product_list'),
    path('search/', views.ProductSearchView.as_view(), name='product_search'),
    path('product/new/', views.ProductCreateView.as_view(), name='product_create'),
    path('product/<uuid:pk>/update/', views.ProductUpdateView.as_view(), name='product_update'),
    path('product/<uuid:pk>/delete/', views.ProductDeleteView.as_view(), name='product_delete'),
    
    path('store/<str:username>/', views.my_store, name='user_store'),
    path('my-store/', views.my_store, name='my_store'),
    
    path('review/<str:review_type>/<uuid:pk>/', views.submit_review, name='submit_review'),
    path('seller/<str:username>/reviews/', AllSellerReviewsView.as_view(), name='all_seller_reviews'),
    path('product/<uuid:pk>/review/<int:review_id>/', views.reply_to_review, name='reply_to_review'),
    path('product/<uuid:pk>/review/<int:review_id>/edit/',views.edit_review, name='edit_review'),
    path('product/<uuid:pk>/review/<int:review_id>/delete/', views.delete_review, name='delete_review'),
    path('product/<uuid:pk>/reply/<int:reply_id>/edit/', views.edit_reply, name='edit_reply'),
    path('product/<uuid:pk>/reply/<int:reply_id>/delete/', views.delete_reply, name='delete_reply'),
    path('product/<uuid:pk>/quick-update/', QuickUpdateView.as_view(), name='product_quick_update'),
    path('report-product/<uuid:product_id>/', ReportProductView.as_view(), name='report_product'),
    
    path('products/toggle-save/', views.toggle_save_product, name='toggle_save_product'),
    path('products/saved/', views.saved_products, name='saved_products'),
    
    path('ajax/generate-ai-description/', views.generate_ai_description, name='generate_ai_description'),
    path('api/subcategories/<int:category_id>/', views.get_subcategories, name='get_subcategories'),
    path('ajax/load-brands/', views.load_brands, name='ajax_load_brands'),
    path('api/subcategories/', views.get_subcategories, name='api_subcategories'),
    path('ajax/load-subcategories/', views.load_subcategories, name='ajax_load_subcategories'),
    path('api/lgas/<int:state_id>/', views.get_lgas, name='get_lgas'),
    path('cookie-policy/', views.cookie_policy_view, name='cookie_policy'),
    ]