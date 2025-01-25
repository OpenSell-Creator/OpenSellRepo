from django.contrib import admin

# Register your models here.
from.models import Profile, location

class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone_number', 'bio', 'location')

class locationadmin(admin.ModelAdmin):
    list_display = ('address', 'district', 'state')

admin.site.register(Profile, ProfileAdmin)
admin.site.register(location, locationadmin)

