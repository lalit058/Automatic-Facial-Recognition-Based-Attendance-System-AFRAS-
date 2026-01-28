from django.contrib import admin
from .models import StaffProfile

@admin.register(StaffProfile)
class StaffProfileAdmin(admin.ModelAdmin):
    # This controls which columns show up in the admin table
    list_display = ('full_name', 'user', 'department', 'designation')
    search_fields = ('full_name', 'user__username', 'department')
    list_filter = ('department', 'designation')