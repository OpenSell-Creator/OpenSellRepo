from django.contrib import admin
from .models import Conversation, Message

class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ('timestamp', 'is_read')
    fields = ('sender', 'content', 'inquiry_type', 'timestamp', 'is_read')

@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('id', 'get_content_info', 'get_participants', 'updated_at')
    list_filter = ('content_type', 'updated_at')
    search_fields = ('participants__user__username',)
    inlines = [MessageInline]
    readonly_fields = ('created_at', 'updated_at', 'content_type', 'object_id')

    def get_content_info(self, obj):
        """Display what this conversation is about"""
        try:
            content_obj = obj.content_object
            content_type = obj.get_content_type_display()
            
            if content_obj:
                if hasattr(content_obj, 'title'):
                    return f"{content_type}: {content_obj.title[:50]}"
                return f"{content_type}: {str(content_obj)[:50]}"
            return f"{content_type}: [Deleted]"
        except Exception:
            return "Unknown"
    get_content_info.short_description = 'About'

    def get_participants(self, obj):
        """Display conversation participants"""
        try:
            return ", ".join([p.user.username for p in obj.participants.all()])
        except Exception:
            return "Unknown"
    get_participants.short_description = 'Participants'

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'get_conversation_info', 'sender', 'inquiry_type', 'timestamp', 'is_read')
    list_filter = ('inquiry_type', 'is_read', 'timestamp')
    search_fields = ('sender__user__username',)
    readonly_fields = ('timestamp', 'encrypted_content')
    
    def get_conversation_info(self, obj):
        """Display conversation context"""
        try:
            conv = obj.conversation
            content_obj = conv.content_object
            if content_obj and hasattr(content_obj, 'title'):
                return f"{conv.get_content_type_display()}: {content_obj.title[:30]}"
            return f"Conversation #{conv.id}"
        except Exception:
            return "Unknown"
    get_conversation_info.short_description = 'Conversation'
    
    def get_queryset(self, request):
        """Optimize queries"""
        qs = super().get_queryset(request)
        return qs.select_related('conversation', 'sender__user')