from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Sum
from decimal import Decimal
from .models import Profile, CreditPackage, CreditsLedger, PackagePurchase


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = [
        'organization_name', 'user_email', 'size', 'credits_balance_display',
        'currency', 'registration_number', 'created_at'
    ]
    list_filter = ['size', 'currency', 'created_at']
    search_fields = [
        'organization_name', 'user__email', 'user__first_name',
        'user__last_name', 'registration_number', 'area_of_focus'
    ]
    readonly_fields = ['id', 'version', 'created_at', 'updated_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Organization Information', {
            'fields': ('id', 'user', 'organization_name', 'size', 'about', 'area_of_focus')
        }),
        ('Registration', {
            'fields': ('registration_number',)
        }),
        ('Credits & Finance', {
            'fields': ('current_credits_balance', 'currency', 'version')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'Email'
    user_email.admin_order_field = 'user__email'

    def credits_balance_display(self, obj):
        balance = float(obj.current_credits_balance)
        color = 'green' if balance > 0 else 'red' if balance < 0 else 'gray'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} {}</span>',
            color, balance, obj.currency
        )
    credits_balance_display.short_description = 'Credits Balance'
    credits_balance_display.admin_order_field = 'current_credits_balance'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


@admin.register(CreditPackage)
class CreditPackageAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'credits_amount', 'price_display', 'patient_limit',
        'is_active_badge', 'display_order', 'total_purchases'
    ]
    list_filter = ['is_active', 'currency', 'created_at']
    search_fields = ['name', 'description']
    # Remove list_editable or ensure fields are in list_display
    readonly_fields = ['id', 'created_at', 'updated_at', 'purchase_stats']
    ordering = ['display_order', 'name']
    
    fieldsets = (
        ('Package Details', {
            'fields': ('id', 'name', 'description', 'patient_limit')
        }),
        ('Credits & Pricing', {
            'fields': ('credits_amount', 'price', 'currency')
        }),
        ('Display Settings', {
            'fields': ('is_active', 'display_order')
        }),
        ('Statistics', {
            'fields': ('purchase_stats',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def price_display(self, obj):
        return f"{obj.price} {obj.currency}"
    price_display.short_description = 'Price'
    price_display.admin_order_field = 'price'

    def is_active_badge(self, obj):
        if obj.is_active:
            return format_html('<span style="color: green;">✓ Active</span>')
        return format_html('<span style="color: red;">✗ Inactive</span>')
    is_active_badge.short_description = 'Status'

    def total_purchases(self, obj):
        count = obj.purchases.filter(status='Completed').count()
        return format_html('<span style="font-weight: bold;">{}</span>', count)
    total_purchases.short_description = 'Total Sales'

    def purchase_stats(self, obj):
        if not obj.pk:
            return "Save the package first to see statistics."
        
        stats = obj.purchases.filter(status='Completed').aggregate(
            total_sales=Sum('price_paid'),
            total_credits_sold=Sum('credits_amount')
        )
        
        html = f"""
        <div style="padding: 10px; background: #f5f5f5; border-radius: 5px;">
            <p><strong>Total Sales:</strong> {stats['total_sales'] or 0} {obj.currency}</p>
            <p><strong>Total Credits Sold:</strong> {stats['total_credits_sold'] or 0}</p>
            <p><strong>Completed Purchases:</strong> {obj.purchases.filter(status='Completed').count()}</p>
            <p><strong>Pending Purchases:</strong> {obj.purchases.filter(status='Pending').count()}</p>
        </div>
        """
        return format_html(html)
    purchase_stats.short_description = 'Purchase Statistics'


@admin.register(CreditsLedger)
class CreditsLedgerAdmin(admin.ModelAdmin):
    list_display = [
        'organization', 'transaction_type_badge', 'amount_display',
        'balance_after_display', 'created_at'
    ]
    list_filter = ['transaction_type', 'created_at']
    search_fields = [
        'organization__organization_name', 'organization__user__email',
        'description'
    ]
    readonly_fields = [
        'id', 'organization', 'transaction_type', 'amount',
        'balance_before', 'balance_after', 'description',
        'related_appointment', 'related_purchase', 'related_transaction',
        'created_by', 'created_at'
    ]
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Transaction Details', {
            'fields': ('id', 'organization', 'transaction_type', 'description')
        }),
        ('Financial Information', {
            'fields': ('amount', 'balance_before', 'balance_after')
        }),
        ('Related Records', {
            'fields': (
                'related_appointment', 'related_purchase', 'related_transaction'
            )
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at'),
            'classes': ('collapse',)
        }),
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def transaction_type_badge(self, obj):
        colors = {
            'Purchase': 'green',
            'Deduction': 'red',
            'Refund': 'orange',
            'Adjustment': 'blue',
            'Bonus': 'purple'
        }
        color = colors.get(obj.transaction_type, 'black')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.transaction_type
        )
    transaction_type_badge.short_description = 'Type'

    def amount_display(self, obj):
        amount = float(obj.amount)
        color = 'green' if amount > 0 else 'red'
        symbol = '+' if amount > 0 else ''
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}{}</span>',
            color, symbol, amount
        )
    amount_display.short_description = 'Amount'
    amount_display.admin_order_field = 'amount'

    def balance_after_display(self, obj):
        return format_html(
            '<span style="font-weight: bold;">{}</span>',
            float(obj.balance_after)
        )
    balance_after_display.short_description = 'Balance After'
    balance_after_display.admin_order_field = 'balance_after'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'organization__user', 'created_by', 'related_appointment',
            'related_purchase', 'related_transaction'
        )


@admin.register(PackagePurchase)
class PackagePurchaseAdmin(admin.ModelAdmin):
    list_display = [
        'organization', 'credit_package', 'status_badge',
        'credits_amount', 'price_paid_display', 'purchased_at'
    ]
    list_filter = ['status', 'currency', 'created_at', 'purchased_at']
    search_fields = [
        'organization__organization_name', 'organization__user__email',
        'credit_package__name'
    ]
    readonly_fields = [
        'id', 'organization', 'credit_package', 'credits_amount',
        'price_paid', 'currency', 'payment_transaction',
        'purchased_by', 'purchased_at', 'created_at', 'updated_at'
    ]
    # Remove list_editable since status is not in list_display as editable field
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Purchase Information', {
            'fields': ('id', 'organization', 'credit_package', 'purchased_by')
        }),
        ('Package Details', {
            'fields': ('credits_amount', 'price_paid', 'currency')
        }),
        ('Payment', {
            'fields': ('payment_transaction', 'status')
        }),
        ('Timestamps', {
            'fields': ('purchased_at', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def status_badge(self, obj):
        colors = {
            'Pending': 'orange',
            'Completed': 'green',
            'Failed': 'red',
            'Refunded': 'purple'
        }
        color = colors.get(obj.status, 'black')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.status
        )
    status_badge.short_description = 'Status'

    def price_paid_display(self, obj):
        return f"{obj.price_paid} {obj.currency}"
    price_paid_display.short_description = 'Price'
    price_paid_display.admin_order_field = 'price_paid'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'organization__user', 'credit_package',
            'purchased_by', 'payment_transaction'
        )

    def save_model(self, request, obj, form, change):
        if change and 'status' in form.changed_data:
            old_status = PackagePurchase.objects.get(pk=obj.pk).status
            
            # Handle status change through serializer logic
            from django.utils import timezone
            if old_status == 'Pending' and obj.status == 'Completed':
                obj.purchased_at = timezone.now()
        
        super().save_model(request, obj, form, change)