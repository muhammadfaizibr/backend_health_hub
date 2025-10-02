from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Sum, Count, Q
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

from .models import (
    PaymentMethod, Transaction, Refund, AppointmentBilling, WalletLedger, PayoutRequest
)


@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'user_email', 'provider', 'type', 'brand', 'default_badge', 
        'status_badge', 'expires_at', 'created_at'
    ]
    list_filter = ['provider', 'type', 'is_default', 'created_at', 'deleted_at']
    search_fields = ['user__email', 'user__first_name', 'brand']
    readonly_fields = ['id', 'created_at', 'updated_at']
    autocomplete_fields = ['user']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        (_('Payment Method Information'), {
            'fields': ('id', 'user', 'provider', 'type', 'brand')
        }),
        (_('Settings'), {
            'fields': ('is_default', 'expires_at', 'metadata')
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at', 'deleted_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_as_default', 'soft_delete']
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User'
    user_email.admin_order_field = 'user__email'
    
    def default_badge(self, obj):
        if obj.is_default:
            return format_html(
                '<span style="color: white; background-color: #28a745; padding: 3px 10px; border-radius: 3px;">Default</span>'
            )
        return '-'
    default_badge.short_description = 'Default'
    
    def status_badge(self, obj):
        if obj.deleted_at:
            color = '#dc3545'
            text = 'Deleted'
        elif obj.expires_at and obj.expires_at < timezone.now():
            color = '#ffc107'
            text = 'Expired'
        else:
            color = '#28a745'
            text = 'Active'
        
        return format_html(
            '<span style="color: white; background-color: {}; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color, text
        )
    status_badge.short_description = 'Status'
    
    def mark_as_default(self, request, queryset):
        if queryset.count() > 1:
            self.message_user(request, "Please select only one payment method.", level='error')
            return
        
        payment_method = queryset.first()
        PaymentMethod.objects.filter(user=payment_method.user, is_default=True).update(is_default=False)
        payment_method.is_default = True
        payment_method.save()
        
        self.message_user(request, "Payment method set as default.")
    mark_as_default.short_description = "Set as default"
    
    def soft_delete(self, request, queryset):
        updated = queryset.update(deleted_at=timezone.now())
        self.message_user(request, f"{updated} payment method(s) deleted.")
    soft_delete.short_description = "Soft delete selected methods"
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


class RefundInline(admin.TabularInline):
    model = Refund
    extra = 0
    readonly_fields = ['status', 'amount', 'initiated_by', 'created_at']
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'user_email', 'amount_display', 'status_badge', 'purpose', 
        'purpose_type', 'created_at', 'completed_at'
    ]
    list_filter = ['status', 'purpose', 'purpose_type', 'currency', 'created_at']
    search_fields = ['user__email', 'transaction_id_gateway', 'idempotency_key']
    readonly_fields = ['id', 'transaction_id_gateway', 'idempotency_key', 'gateway_response', 'created_at', 'updated_at']
    autocomplete_fields = ['user', 'payment_method', 'receipt_file']
    date_hierarchy = 'created_at'
    inlines = [RefundInline]
    
    fieldsets = (
        (_('Transaction Information'), {
            'fields': ('id', 'transaction_id_gateway', 'idempotency_key', 'user', 'payment_method')
        }),
        (_('Amount & Purpose'), {
            'fields': ('amount', 'currency', 'purpose', 'purpose_id', 'purpose_type')
        }),
        (_('Status'), {
            'fields': ('status', 'failure_reason', 'completed_at')
        }),
        (_('Gateway Response'), {
            'fields': ('gateway_response',),
            'classes': ('collapse',)
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User'
    user_email.admin_order_field = 'user__email'
    
    def amount_display(self, obj):
        return f"{obj.amount} {obj.currency}"
    amount_display.short_description = 'Amount'
    amount_display.admin_order_field = 'amount'
    
    def status_badge(self, obj):
        colors = {
            'Pending': '#6c757d',
            'Processing': '#17a2b8',
            'Success': '#28a745',
            'Failed': '#dc3545',
            'Refunded': '#ffc107',
            'Partially Refunded': '#fd7e14',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="color: white; background-color: {}; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color, obj.status
        )
    status_badge.short_description = 'Status'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'payment_method')


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'transaction_id', 'amount', 'status_badge', 'initiated_by_email', 
        'processed_by_email', 'created_at', 'processed_at'
    ]
    list_filter = ['status', 'created_at', 'processed_at']
    search_fields = ['transaction__transaction_id_gateway', 'refund_id_gateway', 'reason']
    readonly_fields = ['id', 'created_at', 'updated_at']
    autocomplete_fields = ['transaction', 'initiated_by', 'processed_by']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        (_('Refund Information'), {
            'fields': ('id', 'transaction', 'refund_id_gateway', 'amount', 'reason')
        }),
        (_('Status'), {
            'fields': ('status', 'failure_reason')
        }),
        (_('Processing'), {
            'fields': ('initiated_by', 'processed_by', 'processed_at')
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['process_refunds']
    
    def transaction_id(self,obj):
        return str(obj.transaction.id)
    transaction_id.short_description = 'Transaction'
    
    def initiated_by_email(self, obj):
        return obj.initiated_by.email if obj.initiated_by else '-'
    initiated_by_email.short_description = 'Initiated By'
    
    def processed_by_email(self, obj):
        return obj.processed_by.email if obj.processed_by else '-'
    processed_by_email.short_description = 'Processed By'
    
    def status_badge(self, obj):
        colors = {
            'Initiated': '#17a2b8',
            'Processing': '#ffc107',
            'Processed': '#28a745',
            'Failed': '#dc3545',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="color: white; background-color: {}; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color, obj.status
        )
    status_badge.short_description = 'Status'
    
    def process_refunds(self, request, queryset):
        initiated_refunds = queryset.filter(status='Initiated')
        count = 0
        
        for refund in initiated_refunds:
            refund.status = 'Processed'
            refund.processed_at = timezone.now()
            refund.processed_by = request.user
            refund.save()
            count += 1
        
        self.message_user(request, f"{count} refund(s) processed successfully.")
    process_refunds.short_description = "Process selected refunds"
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'transaction__user', 'initiated_by', 'processed_by'
        )


@admin.register(AppointmentBilling)
class AppointmentBillingAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'appointment_id', 'organization_name', 'doctor_name', 
        'total_amount_display', 'status_badge', 'billed_at', 'created_at'
    ]
    list_filter = ['status', 'currency', 'created_at', 'billed_at']
    search_fields = [
        'appointment__id', 'organization__user__email', 
        'doctor__user__email', 'translator__user__email'
    ]
    readonly_fields = ['id', 'total_amount', 'created_at', 'updated_at']
    autocomplete_fields = ['appointment', 'organization', 'doctor', 'translator']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        (_('Appointment & Parties'), {
            'fields': ('id', 'appointment', 'organization', 'doctor', 'translator')
        }),
        (_('Fees'), {
            'fields': ('doctor_fee', 'translator_fee', 'platform_fee', 'platform_fee_percentage', 'total_amount', 'currency')
        }),
        (_('Status'), {
            'fields': ('status', 'billed_at')
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_as_billed']
    
    def appointment_id(self, obj):
        return str(obj.appointment.id)
    appointment_id.short_description = 'Appointment'
    
    def organization_name(self, obj):
        return obj.organization.user.email
    organization_name.short_description = 'Organization'
    organization_name.admin_order_field = 'organization__user__email'
    
    def doctor_name(self, obj):
        return obj.doctor.user.get_full_name()
    doctor_name.short_description = 'Doctor'
    doctor_name.admin_order_field = 'doctor__user__first_name'
    
    def total_amount_display(self, obj):
        return f"{obj.total_amount} {obj.currency}"
    total_amount_display.short_description = 'Total'
    total_amount_display.admin_order_field = 'total_amount'
    
    def status_badge(self, obj):
        colors = {
            'Draft': '#6c757d',
            'Billed': '#28a745',
            'Cancelled': '#dc3545',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="color: white; background-color: {}; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color, obj.status
        )
    status_badge.short_description = 'Status'
    
    def mark_as_billed(self, request, queryset):
        draft_billings = queryset.filter(status='Draft')
        updated = draft_billings.update(status='Billed', billed_at=timezone.now())
        self.message_user(request, f"{updated} billing(s) marked as billed.")
    mark_as_billed.short_description = "Mark as billed"
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'appointment', 'organization__user', 'doctor__user', 'translator__user'
        )


@admin.register(WalletLedger)
class WalletLedgerAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'wallet_user', 'transaction_type_badge', 'amount', 
        'balance_after', 'status_badge', 'created_at'
    ]
    list_filter = ['transaction_type', 'status', 'balance_type', 'created_at']
    search_fields = ['wallet__user__email', 'description']
    readonly_fields = ['id', 'balance_before', 'balance_after', 'created_at']
    autocomplete_fields = ['wallet', 'related_appointment', 'related_billing', 'related_payout', 'created_by']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        (_('Ledger Entry'), {
            'fields': ('id', 'wallet', 'transaction_type', 'amount', 'balance_type', 'status')
        }),
        (_('Balance'), {
            'fields': ('balance_before', 'balance_after')
        }),
        (_('Related Records'), {
            'fields': ('related_appointment', 'related_billing', 'related_payout'),
            'classes': ('collapse',)
        }),
        (_('Details'), {
            'fields': ('description', 'available_at', 'created_by')
        }),
        (_('Timestamps'), {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def wallet_user(self, obj):
        return obj.wallet.user.email
    wallet_user.short_description = 'User'
    wallet_user.admin_order_field = 'wallet__user__email'
    
    def transaction_type_badge(self, obj):
        colors = {
            'Earning': '#28a745',
            'Withdrawal': '#dc3545',
            'Refund': '#17a2b8',
            'Adjustment': '#ffc107',
        }
        color = colors.get(obj.transaction_type, '#6c757d')
        return format_html(
            '<span style="color: white; background-color: {}; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color, obj.transaction_type
        )
    transaction_type_badge.short_description = 'Type'
    
    def status_badge(self, obj):
        colors = {
            'Pending': '#ffc107',
            'Available': '#28a745',
            'Withdrawn': '#6c757d',
            'Refunded': '#17a2b8',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="color: white; background-color: {}; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color, obj.status
        )
    status_badge.short_description = 'Status'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'wallet__user', 'created_by', 'related_appointment', 'related_billing', 'related_payout'
        )
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PayoutRequest)
class PayoutRequestAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'wallet_user', 'amount_display', 'status_badge', 
        'requested_at', 'processed_at', 'processed_by_email'
    ]
    list_filter = ['status', 'currency', 'requested_at', 'processed_at']
    search_fields = ['wallet__user__email', 'processing_notes', 'failure_reason']
    readonly_fields = ['id', 'requested_at', 'created_at', 'updated_at']
    autocomplete_fields = ['wallet', 'payment_method', 'transaction', 'processed_by']
    date_hierarchy = 'requested_at'
    
    fieldsets = (
        (_('Payout Information'), {
            'fields': ('id', 'wallet', 'amount', 'currency', 'payment_method')
        }),
        (_('Bank Details'), {
            'fields': ('bank_details',),
            'classes': ('collapse',)
        }),
        (_('Status'), {
            'fields': ('status', 'transaction', 'failure_reason')
        }),
        (_('Processing'), {
            'fields': ('processing_notes', 'processed_by', 'processed_at')
        }),
        (_('Timestamps'), {
            'fields': ('requested_at', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_as_completed', 'mark_as_failed']
    
    def wallet_user(self, obj):
        return obj.wallet.user.email
    wallet_user.short_description = 'User'
    wallet_user.admin_order_field = 'wallet__user__email'
    
    def amount_display(self, obj):
        return f"{obj.amount} {obj.currency}"
    amount_display.short_description = 'Amount'
    amount_display.admin_order_field = 'amount'
    
    def processed_by_email(self, obj):
        return obj.processed_by.email if obj.processed_by else '-'
    processed_by_email.short_description = 'Processed By'
    
    def status_badge(self, obj):
        colors = {
            'Pending': '#ffc107',
            'Processing': '#17a2b8',
            'Completed': '#28a745',
            'Failed': '#dc3545',
            'Cancelled': '#6c757d',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="color: white; background-color: {}; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color, obj.status
        )
    status_badge.short_description = 'Status'
    
    def mark_as_completed(self, request, queryset):
        pending_payouts = queryset.filter(status__in=['Pending', 'Processing'])
        count = pending_payouts.update(
            status='Completed',
            processed_at=timezone.now(),
            processed_by=request.user
        )
        self.message_user(request, f"{count} payout(s) marked as completed.")
    mark_as_completed.short_description = "Mark as completed"
    
    def mark_as_failed(self, request, queryset):
        pending_payouts = queryset.filter(status__in=['Pending', 'Processing'])
        count = pending_payouts.update(
            status='Failed',
            processed_at=timezone.now(),
            processed_by=request.user
        )
        self.message_user(request, f"{count} payout(s) marked as failed.")
    mark_as_failed.short_description = "Mark as failed"
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'wallet__user', 'payment_method', 'transaction', 'processed_by'
        )