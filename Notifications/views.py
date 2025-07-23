# notifications/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.generic import ListView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.views import View
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from datetime import timedelta
from django.db.models import Q, Count
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.contrib.contenttypes.models import ContentType
from django.core.paginator import Paginator
from django.conf import settings
import json

from .models import Notification, NotificationPreference, NotificationCategory, mark_all_read
from Home.models import Product_Listing, Review, SavedProduct


def notification_counts(request):
    """Context processor for notification counts"""
    if request.user.is_authenticated:
        unread_count = Notification.objects.filter(
            recipient=request.user,
            is_read=False
        ).count()
        return {'unread_notifications_count': unread_count}
    return {'unread_notifications_count': 0}


class NotificationListView(LoginRequiredMixin, ListView):
    model = Notification
    template_name = 'notifications/notification_list.html'
    context_object_name = 'notifications'
    paginate_by = 15
    
    def get_queryset(self):
        queryset = Notification.objects.filter(
            recipient=self.request.user
        ).select_related('content_type').order_by('-created_at')
        
        # Filter by category if specified
        category = self.request.GET.get('category')
        if category and category != 'all':
            queryset = queryset.filter(category=category)
        
        # Filter by read status
        read_status = self.request.GET.get('read')
        if read_status == 'unread':
            queryset = queryset.filter(is_read=False)
        elif read_status == 'read':
            queryset = queryset.filter(is_read=True)
            
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get unique categories that exist for this user - FIXED
        user_categories = Notification.objects.filter(
            recipient=self.request.user
        ).values('category').distinct().order_by('category')
        
        # Create category choices without duplicates
        category_choices = []
        seen_categories = set()
        
        for cat_dict in user_categories:
            category = cat_dict['category']
            if category and category not in seen_categories:
                # Get display name from choices
                display_name = None
                for choice_value, choice_display in NotificationCategory.choices:
                    if choice_value == category:
                        display_name = choice_display
                        break
                
                if display_name:
                    category_choices.append((category, display_name))
                    seen_categories.add(category)
        
        context['categories'] = category_choices
        context['current_category'] = self.request.GET.get('category', 'all')
        context['current_read_status'] = self.request.GET.get('read', 'all')
        
        return context


class NotificationDetailView(LoginRequiredMixin, DetailView):
    model = Notification
    template_name = 'notifications/notification_detail.html'
    context_object_name = 'notification'
    
    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user)
    
    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        
        # Mark as read when viewed
        if not obj.is_read:
            obj.mark_as_read()
        
        return obj
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add related content information
        if self.object.content_object:
            context['content_type'] = self.object.get_content_type_name()
            
            # Add specific context based on content type
            if self.object.get_content_type_name() == 'product_listing':
                if hasattr(self.object.content_object, 'get_absolute_url'):
                    context['product_url'] = self.object.content_object.get_absolute_url()
            elif self.object.get_content_type_name() == 'review':
                if hasattr(self.object.content_object, 'product') and self.object.content_object.product:
                    if hasattr(self.object.content_object.product, 'get_absolute_url'):
                        context['product_url'] = self.object.content_object.product.get_absolute_url()
        
        return context


@login_required
def notification_preferences(request):
    """Handle notification preferences"""
    preferences, created = NotificationPreference.objects.get_or_create(
        user=request.user
    )
    
    if request.method == 'POST':
        # Update preferences based on form data
        preferences.review_notifications = request.POST.get('review_notifications') == 'on'
        preferences.save_notifications = request.POST.get('save_notifications') == 'on'
        preferences.view_milestone_notifications = request.POST.get('view_milestone_notifications') == 'on'
        preferences.system_notifications = request.POST.get('system_notifications') == 'on'
        preferences.deletion_warnings = request.POST.get('deletion_warnings') == 'on'
        preferences.stock_alerts = request.POST.get('stock_alerts') == 'on'
        preferences.price_drop_alerts = request.POST.get('price_drop_alerts') == 'on'
        preferences.reply_notifications = request.POST.get('reply_notifications') == 'on'
        preferences.report_notifications = request.POST.get('report_notifications') == 'on'
        preferences.milestone_achievements = request.POST.get('milestone_achievements') == 'on'
        preferences.email_notifications = request.POST.get('email_notifications') == 'on'
        preferences.email_digest = request.POST.get('email_digest') == 'on'
        preferences.push_notifications = request.POST.get('push_notifications') == 'on'
        preferences.frequency = request.POST.get('frequency', 'instant')
        
        preferences.save()
        messages.success(request, 'Your notification preferences have been updated successfully!')
        return redirect('notifications:preferences')
    
    context = {
        'preferences': preferences
    }
    return render(request, 'notifications/preferences.html', context)


@require_POST
@login_required
def mark_notification_read(request, notification_id):
    """Mark a specific notification as read"""
    try:
        notification = get_object_or_404(
            Notification, 
            id=notification_id, 
            recipient=request.user
        )
        notification.mark_as_read()
        
        return JsonResponse({
            'status': 'success',
            'message': 'Notification marked as read'
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


@require_POST
@login_required
def mark_all_notifications_read(request):
    """Mark all notifications as read for the current user"""
    try:
        count = mark_all_read(request.user)
        
        return JsonResponse({
            'status': 'success',
            'message': f'{count} notifications marked as read',
            'count': count
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


@require_POST
@login_required
def clear_all_notifications(request):
    """Delete all notifications for the current user"""
    try:
        count = Notification.objects.filter(recipient=request.user).count()
        Notification.objects.filter(recipient=request.user).delete()
        
        return JsonResponse({
            'status': 'success',
            'message': f'{count} notifications cleared',
            'count': count
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


@require_POST
@login_required
def delete_notification(request, notification_id):
    """Delete a specific notification"""
    try:
        notification = get_object_or_404(
            Notification,
            id=notification_id,
            recipient=request.user
        )
        notification.delete()
        
        return JsonResponse({
            'status': 'success',
            'message': 'Notification deleted'
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


@login_required
def notification_stats(request):
    """Get notification statistics for the user"""
    user_notifications = Notification.objects.filter(recipient=request.user)
    
    stats = {
        'total': user_notifications.count(),
        'unread': user_notifications.filter(is_read=False).count(),
        'read': user_notifications.filter(is_read=True).count(),
        'today': user_notifications.filter(
            created_at__date=timezone.now().date()
        ).count(),
        'this_week': user_notifications.filter(
            created_at__gte=timezone.now() - timedelta(days=7)
        ).count(),
        'by_category': {}
    }
    
    # Get stats by category
    for category, display_name in NotificationCategory.choices:
        count = user_notifications.filter(category=category).count()
        if count > 0:
            stats['by_category'][category] = {
                'count': count,
                'display_name': display_name
            }
    
    return JsonResponse(stats)


class NotificationAPIView(LoginRequiredMixin, View):
    """API endpoint for notifications (for AJAX requests)"""
    
    def get(self, request):
        """Get notifications for the user"""
        notifications = Notification.objects.filter(
            recipient=request.user
        ).order_by('-created_at')[:10]  # Latest 10
        
        data = []
        for notification in notifications:
            data.append({
                'id': notification.id,
                'title': notification.title,
                'message': notification.message,
                'category': notification.category,
                'priority': notification.priority,
                'is_read': notification.is_read,
                'created_at': notification.created_at.isoformat(),
                'icon': notification.get_icon(),
                'url': reverse('notifications:detail', args=[notification.id])
            })
        
        return JsonResponse({
            'notifications': data,
            'unread_count': Notification.objects.filter(
                recipient=request.user, 
                is_read=False
            ).count()
        })


# Utility function to call from product detail view
def track_product_view(request, product):
    """
    Call this function from your product detail view to track views
    and send milestone notifications
    """
    if not request.user.is_authenticated:
        return
    
    # Increment view count (assuming you have a views field)
    if hasattr(product, 'views'):
        product.views += 1
        product.save(update_fields=['views'])
        
        # Import here to avoid circular imports
        from .signals import check_view_milestones
        check_view_milestones(product, product.views)


# Bulk notification utilities
@login_required
def send_bulk_notification(request):
    """Admin function to send notifications to multiple users"""
    if not request.user.is_staff:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    if request.method == 'POST':
        data = json.loads(request.body)
        
        title = data.get('title')
        message = data.get('message')
        category = data.get('category', NotificationCategory.ANNOUNCEMENT)
        user_ids = data.get('user_ids', [])
        
        if not title or not message:
            return JsonResponse({'error': 'Title and message are required'}, status=400)
        
        # Create notifications for specified users
        from django.contrib.auth.models import User
        from .models import create_bulk_notification
        
        if user_ids:
            users = User.objects.filter(id__in=user_ids)
        else:
            users = User.objects.all()
        
        notifications = create_bulk_notification(users, title, message, category)
        
        return JsonResponse({
            'status': 'success',
            'count': len(notifications)
        })
    
    return JsonResponse({'error': 'Invalid request method'}, status=405)


# Push notification subscription (for PWA)
@require_POST
@login_required
def subscribe_push(request):
    """Handle push notification subscription"""
    try:
        data = json.loads(request.body)
        subscription_info = data.get('subscription')
        
        # Store subscription info in user preferences or separate model
        preferences, created = NotificationPreference.objects.get_or_create(
            user=request.user
        )
        
        # You might want to create a separate PushSubscription model
        # For now, we'll just enable push notifications
        preferences.push_notifications = True
        preferences.save()
        
        return JsonResponse({
            'status': 'success',
            'message': 'Push notifications enabled'
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


@require_POST
@login_required
def unsubscribe_push(request):
    """Handle push notification unsubscription"""
    try:
        preferences = NotificationPreference.objects.get(user=request.user)
        preferences.push_notifications = False
        preferences.save()
        
        return JsonResponse({
            'status': 'success',
            'message': 'Push notifications disabled'
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)