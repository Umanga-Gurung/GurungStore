from django.db import models
from app.models import Account
from store.models import Product
from django.utils import timezone
import random


class Payment(models.Model):
    user = models.ForeignKey(Account, on_delete=models.CASCADE)
    payment_id = models.CharField(max_length=100)
    payment_method = models.CharField(max_length=100)
    amount_paid = models.CharField(max_length=100)
    status = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.payment_id

class Order(models.Model):
    STATUS ={
        ('New', 'New'),
        ('Accepted', 'Accepted'),
        ('Completed', 'Completed'),
        ('Cancelled', 'Cancelled'),
    }        

    DELIVERY_STATUS_CHOICES = (
        ('Pending', 'Pending Assignment'),
        ('Assigned', 'Assigned to Delivery Person'),
        ('Out for Delivery', 'Out for Delivery'),
        ('OTP Sent', 'OTP Sent to Customer'),
        ('Completed', 'Delivery Completed & Verified'),
    )

    user = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True)
    payment = models.ForeignKey(Payment, on_delete=models.SET_NULL, null=True, blank=True)
    order_number = models.CharField(max_length=100, default="", null=True)
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    phone_number = models.CharField(max_length=20)
    email = models.EmailField(max_length=100)
    address_line_1 = models.CharField(max_length=100)
    address_line_2 = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=50)
    order_note = models.CharField(max_length=100,blank=True)
    order_total = models.CharField(max_length=30, default="", null=True)
    status = models.CharField(max_length=10, choices=STATUS, default="New")
    ip = models.CharField(blank=True ,max_length=10,  default="", null=True)
    is_ordered = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    update_at = models.DateTimeField(auto_now=True)

    # Delivery fields
    delivery_person = models.ForeignKey(
        Account, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='delivery_orders'
    )
    delivery_status = models.CharField(
        max_length=30, choices=DELIVERY_STATUS_CHOICES, default='Pending'
    )
    delivery_otp = models.CharField(max_length=6, blank=True, null=True)
    otp_created_at = models.DateTimeField(blank=True, null=True)

    def full_name(self):
        return f'{self.first_name} {self.last_name}'
     
    def full_address(self):
        return f'{self.address_line_1} {self.address_line_2}'

    def generate_delivery_otp(self):
        """Generate a 6-digit OTP and record the creation timestamp."""
        self.delivery_otp = str(random.randint(100000, 999999))
        self.otp_created_at = timezone.now()
        self.save()
        return self.delivery_otp

    def verify_delivery_otp(self, input_otp):
        """Verify the OTP matches and has not expired (15-minute window)."""
        if not self.delivery_otp or not self.otp_created_at:
            return False
        if self.delivery_otp != str(input_otp):
            return False
        elapsed = (timezone.now() - self.otp_created_at).total_seconds()
        if elapsed > 900:  # 15 minutes
            return False
        return True

    def __str__(self):
        return self.first_name
    
class OrderProduct(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    user = models.ForeignKey(Account, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)    
    quantity = models.IntegerField()
    product_price = models.FloatField()
    ordered = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.product.product_name
    
    
    
    