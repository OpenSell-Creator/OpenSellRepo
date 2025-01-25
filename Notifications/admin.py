from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.contrib.contenttypes.models import ContentType
from .models import Notification, NotificationPreference

class NotificationPreferenceInline(admin.StackedInline):
    model = NotificationPreference
    can_delete = False
    verbose_name_plural = 'Notification Preferences'

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('recipient', 'title', 'category', 'is_read', 'created_at', 'linked_content')
    list_filter = ('category', 'is_read', 'created_at')
    search_fields = ('recipient__username', 'title', 'message')
    readonly_fields = ('created_at',)
    raw_id_fields = ('recipient',)
    
    fieldsets = (
        (None, {
            'fields': ('recipient', 'title', 'message')
        }),
        ('Category & Status', {
            'fields': ('category', 'is_read')
        }),
        ('Content Link', {
            'fields': ('content_type', 'object_id'),
            'classes': ('collapse',),
            'description': 'Optional: Link this notification to a specific object'
        })
    )

    def linked_content(self, obj):
        if obj.content_type and obj.object_id:
            content_type = ContentType.objects.get_for_id(obj.content_type.id)
            try:
                linked_obj = content_type.get_object_for_this_type(id=obj.object_id)
                url = reverse(
                    f'admin:{content_type.app_label}_{content_type.model}_change',
                    args=[obj.object_id]
                )
                return format_html('<a href="{}">{} ({})</a>', 
                    url, 
                    str(linked_obj), 
                    content_type.model.title()
                )
            except:
                return "Invalid Link"
        return "-"
    linked_content.short_description = "Linked Content"

@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ('user', 'review_notifications', 'save_notifications', 
                   'view_milestone_notifications', 'system_notifications')
    list_filter = ('review_notifications', 'save_notifications', 
                  'view_milestone_notifications', 'system_notifications')
    search_fields = ('user__username',)
    raw_id_fields = ('user',)

    def has_add_permission(self, request):
        # Prevent creating preferences directly - they should be created with users
        return False