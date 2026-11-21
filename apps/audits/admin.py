from django.contrib import admin
from apps.locations.models import Company, Location
from apps.devices.models import DeviceCategory, DeviceType
from apps.audits.models import AuditSession, AuditItem
from apps.common.models import SystemActivityLog

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('name', 'short_code', 'is_active', 'created_at')
    search_fields = ('name', 'short_code')


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'location_type', 'in_charge_name', 'is_active')
    list_filter = ('location_type', 'company', 'is_active')
    search_fields = ('name', 'code', 'in_charge_name')


@admin.register(DeviceCategory)
class DeviceCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'order', 'is_active')
    ordering = ('order',)


@admin.register(DeviceType)
class DeviceTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'order', 'is_active')
    list_filter = ('category', 'is_active')
    search_fields = ('name',)
    ordering = ('category__order', 'order', 'name')


class AuditItemInline(admin.TabularInline):
    model = AuditItem
    extra = 0
    fields = ('device_type', 'active_qty', 'backup_qty', 'faulty_qty', 'total_qty', 'remarks')
    readonly_fields = ('total_qty',)


@admin.register(AuditSession)
class AuditSessionAdmin(admin.ModelAdmin):
    list_display = ('location', 'audit_date', 'auditor_name', 'status', 'total_qty', 'created_at')
    list_filter = ('status', 'location__location_type', 'audit_date')
    search_fields = ('location__name', 'auditor_name', 'remarks')
    inlines = [AuditItemInline]


@admin.register(AuditItem)
class AuditItemAdmin(admin.ModelAdmin):
    list_display = ('device_type', 'audit_session', 'active_qty', 'backup_qty', 'faulty_qty', 'total_qty')
    list_filter = ('device_type__category', 'audit_session__location')
    search_fields = ('device_type__name', 'audit_session__location__name')


@admin.register(SystemActivityLog)
class SystemActivityLogAdmin(admin.ModelAdmin):
    list_display = ('action', 'module', 'user_name', 'created_at')
    list_filter = ('module', 'action')
    readonly_fields = ('created_at', 'updated_at')
