from django.contrib import admin
from .models import Account, UserProfile
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
# Register your models here.

class AccountManager(UserAdmin):
    list_display = ['first_name','last_name','username','email','is_delivery_person','last_login']
    filter_horizontal = ()
    list_filter = ('is_delivery_person',)
    fieldsets = ()
        


class UserProfileManager(admin.ModelAdmin):
    def thumbnail(self, obj):
        if obj.profile_pic:
            return format_html('<img src="{}" width="30" style="border-radius:50%">', obj.profile_pic.url)
        return "-"

    thumbnail.short_description = "Profile Pic"
    list_display = ['thumbnail','user', 'city']


admin.site.register(Account, AccountManager)
admin.site.register(UserProfile, UserProfileManager)