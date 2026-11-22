from django.contrib import admin
from .models import (
    Vendor, VendorContact, VendorContract, VendorRMA, VendorEvaluation, VendorDocument
)


class VendorContactInline(admin.TabularInline):
    model = VendorContact
    extra = 1


class VendorDocumentInline(admin.TabularInline):
    model = VendorDocument
    extra = 1


@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ('vendor_code', 'name', 'category', 'status', 'overall_rating', 'phone', 'city')
    list_filter = ('category', 'status', 'city')
    search_fields = ('name', 'vendor_code', 'bin_tin_number', 'email', 'phone')
    inlines = [VendorContactInline, VendorDocumentInline]


@admin.register(VendorContract)
class VendorContractAdmin(admin.ModelAdmin):
    list_display = ('contract_number', 'title', 'vendor', 'contract_type', 'start_date', 'end_date', 'status', 'contract_value')
    list_filter = ('contract_type', 'status')
    search_fields = ('contract_number', 'title', 'vendor__name')
    filter_horizontal = ('covered_assets',)


@admin.register(VendorRMA)
class VendorRMAAdmin(admin.ModelAdmin):
    list_display = ('rma_number', 'asset', 'vendor', 'location', 'dispatch_date', 'status', 'standby_provided')
    list_filter = ('status', 'standby_provided', 'location')
    search_fields = ('rma_number', 'asset__asset_tag', 'vendor__name', 'challan_reference')


@admin.register(VendorEvaluation)
class VendorEvaluationAdmin(admin.ModelAdmin):
    list_display = ('vendor', 'review_period', 'composite_score', 'evaluated_by', 'created_at')
    list_filter = ('review_period',)
