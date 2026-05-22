from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import (User, Company, Worker, WorkerChild, Form101, Form106,
                     Project, ProjectFile, AttendanceRecord, PayrollRecord,
                     MaterialInvoice, Freelancer, FreelancerPayment,
                     PayrollTaxBracket, PayrollSetting)

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


# ── Payroll tax brackets & settings (owner-editable) ──────────────────────

@admin.register(PayrollTaxBracket)
class PayrollTaxBracketAdmin(admin.ModelAdmin):
    list_display  = ['bracket_index', 'ceiling_display', 'rate_display', 'notes', 'updated_at']
    list_editable = ['notes']
    ordering      = ['bracket_index']
    fields        = ['bracket_index', 'ceiling', 'rate', 'notes']

    def ceiling_display(self, obj):
        return f'₪{obj.ceiling:,.0f}' if obj.ceiling else 'ללא תקרה (אינסוף)'
    ceiling_display.short_description = 'תקרה'

    def rate_display(self, obj):
        return f'{float(obj.rate) * 100:g}%'
    rate_display.short_description = 'שיעור'

    def has_delete_permission(self, request, obj=None):
        # Don't let anyone delete brackets — must always have at least 7.
        return False


@admin.register(PayrollSetting)
class PayrollSettingAdmin(admin.ModelAdmin):
    list_display  = ['setting_key', 'setting_value', 'notes', 'updated_at']
    list_editable = ['setting_value', 'notes']
    ordering      = ['setting_key']
    search_fields = ['setting_key']

    def has_add_permission(self, request):
        # Only the seeded keys — adding random keys won't do anything anyway.
        return False

    def has_delete_permission(self, request, obj=None):
        return False