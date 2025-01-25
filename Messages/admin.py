from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import Conversation, Message

class MessageInline(admin.TabularInline):
    model = Message
    extra = 0

@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('id', 'product', 'get_participants', 'updated_at')
    list_filter = ('product', 'updated_at')
    search_fields = ('product__title', 'participants__user__username')
    inlines = [MessageInline]

    def get_participants(self, obj):
        return ", ".join([p.user.username for p in obj.participants.all()])
    get_participants.short_description = 'Participants'

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'conversation', 'sender', 'inquiry_type', 'timestamp', 'is_read')
    list_filter = ('inquiry_type', 'is_read', 'timestamp')
    search_fields = ('content', 'sender__user__username', 'conversation__product__title')