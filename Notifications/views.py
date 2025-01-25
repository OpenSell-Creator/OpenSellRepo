from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.contrib.contenttypes.models import ContentType
from .models import Notification, NotificationPreference, NotificationCategory
from Home.models import Product_Listing, Review, SavedProduct

class NotificationListView(LoginRequiredMixin, ListView):
    model = Notification
    template_name = 'notifications/notification_list.html'
    context_object_name = 'notifications'
    paginate_by = 10

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['unread_count'] = self.get_queryset().filter(is_read=False).count()
        context['categories'] = NotificationCategory.choices
        return context

@login_required
def mark_notification_read(request, notification_id):
    try:
        notification = Notification.objects.get(id=notification_id, recipient=request.user)
        notification.is_read = True
        notification.save()
        return JsonResponse({'status': 'success'})
    except Notification.DoesNotExist:
        return JsonResponse({'status': 'error'}, status=404)

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