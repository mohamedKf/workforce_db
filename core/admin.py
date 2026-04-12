from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import (User, Company, Worker, WorkerChild, Form101, Form106,
                     Project, ProjectFile, AttendanceRecord, PayrollRecord,
                     MaterialInvoice, Freelancer, FreelancerPayment)

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display  = ['id_number', 'full_name', 'role', 'is_active']
    list_filter   = ['role', 'is_active']
    search_fields = ['id_number', 'full_name', 'phone']
    ordering      = ['full_name']
    fieldsets = (
        (None, {'fields': ('id_number', 'password')}),
        ('פרטים אישיים', {'fields': ('full_name', 'phone', 'role')}),
        ('הרשאות', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
    )
    add_fieldsets = (
        (None, {'classes': ('wide',), 'fields': ('id_number', 'full_name', 'role', 'password1', 'password2')}),
    )

admin.register(Company)(admin.ModelAdmin)
admin.register(Worker)(admin.ModelAdmin)
admin.register(WorkerChild)(admin.ModelAdmin)
admin.register(Project)(admin.ModelAdmin)
admin.register(AttendanceRecord)(admin.ModelAdmin)
admin.register(PayrollRecord)(admin.ModelAdmin)
admin.register(MaterialInvoice)(admin.ModelAdmin)
admin.register(Freelancer)(admin.ModelAdmin)
admin.register(FreelancerPayment)(admin.ModelAdmin)
