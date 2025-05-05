from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.views.generic import ListView, DetailView
from django.views import View
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from datetime import timedelta
from django.db.models import Q
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.dispatch import receiver
from django.contrib import messages
from django.contrib.contenttypes.models import ContentType
from .models import Notification, NotificationPreference, NotificationCategory
from Home.models import Product_Listing, Review, SavedProduct


def notification_counts(request):
    if request.user.is_authenticated:
        unread_notifications_count = Notification.objects.filter(
            recipient=request.user,
            is_read=False
        ).count()
        return {
            'unread_notifications_count': unread_notifications_count
        }
    return {
        'unread_notifications_count': 0
    }

class NotificationListView(LoginRequiredMixin, ListView):
    model = Notification
    template_name = 'notifications/notification_list.html'
    context_object_name = 'notifications'
    paginate_by = 10
    
    def get_queryset(self):
        return Notification.objects.filter(
            recipient=self.request.user
        ).order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add unread count
        context['unread_count'] = self.get_queryset().filter(is_read=False).count()
        
        # Add categories
        context['categories'] = NotificationCategory.choices
        
        # Find editable notifications
        editable_notifications = []
        for notification in context['notifications']:
            obj = notification.content_object
            try:
                # Check if obj exists and has necessary attributes
                if (obj and hasattr(obj, 'seller') and 
                    obj.seller and hasattr(obj.seller, 'user') and 
                    obj.seller.user == self.request.user):
                    editable_notifications.append({
                        'id': notification.id,
                        'edit_url': reverse('product_update', args=[obj.id])
                    })
            except AttributeError:
                # Skip this notification if any attribute access fails
                continue
        
        context['editable_notifications'] = editable_notifications
        return context
    
    
class NotificationDetailView(LoginRequiredMixin, DetailView):
    model = Notification
    template_name = 'notifications/notification_detail.html'
    context_object_name = 'notification'

    def get_queryset(self):
        return super().get_queryset().filter(recipient=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        notification = self.object
        
        try:
            # Get content object (e.g., product)
            content_obj = notification.content_object
            
            # Add content type for template conditions
            if content_obj:
                context['content_type'] = content_obj._meta.model_name
            
            # Add URL context if it's a product
            if content_obj and hasattr(content_obj, 'get_absolute_url'):
                context['product_url'] = content_obj.get_absolute_url()
            
            # Add editable notifications if applicable
            if (content_obj and 
                hasattr(content_obj, 'seller') and 
                content_obj.seller and 
                hasattr(content_obj.seller, 'user') and 
                content_obj.seller.user == self.request.user):
                context['editable_notifications'] = [{
                    'id': notification.id,
                    'edit_url': reverse('product_update', args=[content_obj.id])
                }]
        except AttributeError:
            # Skip adding context if any attribute access fails
            pass
        
        return context
    
    def get(self, request, *args, **kwargs):
        try:
            response = super().get(request, *args, **kwargs)
            if not self.object.is_read:
                self.object.is_read = True
                self.object.save()
            return response
        except AttributeError:
            messages.error(request, "This notification is no longer available.")
            return redirect('notifications:list')

class MarkNotificationAsReadView(View):
    def post(self, request, pk):
        notification = Notification.objects.get(pk=pk, recipient=request.user)
        notification.is_read = True
        notification.save()
        return JsonResponse({'status': 'success'})


@login_required
@require_POST
@csrf_exempt
def mark_notification_read(request, notification_id):
    try:
        notification = Notification.objects.get(id=notification_id, recipient=request.user)
        notification.is_read = True
        notification.save()
        return JsonResponse({'status': 'success'})
    except Notification.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Notification not found'}, status=404)

@login_required
def notification_preferences(request):
    preferences, created = NotificationPreference.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        preferences.review_notifications = request.POST.get('review_notifications') == 'on'
        preferences.save_notifications = request.POST.get('save_notifications') == 'on'
        preferences.view_milestone_notifications = request.POST.get('view_milestone_notifications') == 'on'
        preferences.system_notifications = request.POST.get('system_notifications') == 'on'
        preferences.save()
        return redirect('notifications:list')
    
    return render(request, 'notifications/preferences.html', {'preferences': preferences})

def create_notification(user, title, message, category, content_object=None):
    """Utility function to create notifications"""
    notification = Notification.objects.create(
        recipient=user,
        title=title,
        message=message,
        category=category,
        content_object=content_object
    )
    return notification


def check_listing_notifications():
    # Check for deletion warnings
    listings = Product_Listing.objects.filter(
        Q(expiration_date__lte=timezone.now() + timedelta(days=3)) &
        Q(deletion_warning_sent=False)
    )
    
    for listing in listings:
        listing.send_deletion_warning()

    # Check for low stock notifications
    low_stock_listings = Product_Listing.objects.filter(
        Q(quantity__lte=5) &
        Q(last_stock_notification__lt=timezone.now() - timedelta(days=1))
    )
    
    for listing in low_stock_listings:
        # Send low stock notification
        listing.last_stock_notification = timezone.now()
        listing.save()
        
@login_required
@require_POST
def mark_all_read(request):
    """Mark all notifications as read for the current user"""
    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    return JsonResponse({'status': 'success', 'message': 'All notifications marked as read'})

@login_required
@require_POST
def clear_all_notifications(request):
    """Delete all notifications for the current user"""
    Notification.objects.filter(recipient=request.user).delete()
    return JsonResponse({'status': 'success', 'message': 'All notifications cleared'})