from django.contrib import admin
from .models import Profile, Location, State, LGA

@admin.register(State)
class StateAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name',)

@admin.register(LGA)
class LGAAdmin(admin.ModelAdmin):
    list_display = ('name', 'state', 'is_active')
    list_filter = ('state', 'is_active')
    search_fields = ('name', 'state__name')

@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('address', 'state', 'lga')
    list_filter = ('state', 'lga')
    search_fields = ('address', 'state__name', 'lga__name')

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone_number', 'get_location')
    search_fields = ('user__username', 'phone_number')
    
    def get_location(self, obj):
        return str(obj.location) if obj.location else '-'
    get_location.short_description = 'Location'