from django.contrib import admin
from django import forms
from .models import Order, OrderProduct, Payment
from app.models import Account
# Register your models here.

class OrderProductLine(admin.TabularInline):
    model  = OrderProduct
    extra = 0
    readonly_fields = ['user', 'product', 'quantity', 'product_price', 'ordered']


class OrderAdminForm(forms.ModelForm):
    """Custom form to restrict delivery_person dropdown to delivery personnel only."""
    class Meta:
        model = Order
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'delivery_person' in self.fields:
            self.fields['delivery_person'].queryset = Account.objects.filter(
                is_delivery_person=True, is_active=True
            )


class OrderAdmin(admin.ModelAdmin):
    form = OrderAdminForm
    list_display = [
        'order_number', 'full_name', 'phone_number', 'email', 'city',
        'order_total', 'status', 'delivery_person', 'delivery_status',
        'is_ordered', 'created_at'
    ]
    list_filter = ['is_ordered', 'status', 'delivery_status', 'created_at']
    search_fields = ['order_number', 'first_name', 'last_name', 'phone_number', 'email', 'delivery_person__email', 'delivery_person__first_name']
    list_per_page = 15
    inlines = [OrderProductLine]

    readonly_fields = ['delivery_otp', 'otp_created_at', 'order_number', 'created_at', 'update_at']

    def get_readonly_fields(self, request, obj=None):
        """Make delivery_person and delivery_status read-only after an order is delivered."""
        readonly = list(self.readonly_fields)
        if obj and obj.delivery_status == 'Completed':
            if 'delivery_person' not in readonly:
                readonly.append('delivery_person')
            if 'delivery_status' not in readonly:
                readonly.append('delivery_status')
        return readonly

    fieldsets = (
        ('Order Information', {
            'fields': ('order_number', 'user', 'payment', 'order_total', 'status', 'is_ordered', 'ip', 'created_at', 'update_at')
        }),
        ('Customer Details', {
            'fields': ('first_name', 'last_name', 'phone_number', 'email', 'address_line_1', 'address_line_2', 'city', 'order_note')
        }),
        ('Delivery Management', {
            'fields': ('delivery_person', 'delivery_status', 'delivery_otp', 'otp_created_at'),
            'description': 'Assign a delivery partner and monitor real-time delivery status and OTP verification timestamps.'
        }),
    )

    def save_model(self, request, obj, form, change):
        """Auto-set delivery_status to 'Assigned' when a delivery_person is first assigned."""
        if change and 'delivery_person' in form.changed_data:
            if obj.delivery_person:
                obj.delivery_status = 'Assigned'
            else:
                obj.delivery_status = 'Pending'
        super().save_model(request, obj, form, change)


class PaymentAdmin(admin.ModelAdmin):
    list_display = ['payment_id', 'user', 'payment_method', 'amount_paid', 'status', 'created_at']
    list_filter = ['payment_method', 'status', 'created_at']
    search_fields = ['payment_id', 'user__email', 'user__first_name', 'user__last_name', 'amount_paid']
    list_per_page = 20

admin.site.register(Order, OrderAdmin)
admin.site.register(OrderProduct)
admin.site.register(Payment, PaymentAdmin)
