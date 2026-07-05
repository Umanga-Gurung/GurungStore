from django.shortcuts import render, redirect
from django.contrib import messages, auth
from cart.models import CartItem
from .forms import OrderForm
from .models import Order, OrderProduct, Payment
import datetime
import json
import requests
import hmac
import hashlib
import base64
from django.views.generic import View
from django.urls import reverse
from django.conf import settings
from django.db import transaction
from decimal import Decimal, InvalidOperation
from django.utils import timezone
from django.core.mail import send_mail


def payments(request):
    body = json.loads(request.body)
    order = Order.objects.get(user=request.user, is_ordered=False, order_number=body["orderId"])
    payment = Payment(
        user=request.user,
        payment_id=body["transId"],
        payment_method=body["payment_method"],
        amount_paid=order.order_total,
        status=body["status"],
    )
    payment.save()
    order.payment = payment
    order.is_ordered = True
    order.save()

    cart_items = CartItem.objects.filter(user=request.user)
    for item in cart_items:
        orderproduct = OrderProduct()
        orderproduct.order_id = order.id
        orderproduct.user_id = request.user.id
        orderproduct.product_id = item.product_id
        orderproduct.quantity = item.quantity
        orderproduct.product_price = item.product.price
        orderproduct.ordered = True
        orderproduct.save()

        # Auto-decrement product stock quantity
        product = item.product
        product.stock = max(0, product.stock - item.quantity)
        product.save()

    CartItem.objects.filter(user=request.user).delete()

    data = {
        "order_number": order.order_number,
        "transId": payment.payment_id,
    }
    return render(request, "orders/payments.html")


def place_order(request, total=0, quantity=0):
    current_user = request.user
    cart_items = CartItem.objects.filter(user=current_user)
    cart_count = cart_items.count()
    if cart_count <= 0:
        return redirect("order_complete")
    for cart_item in cart_items:
        total += cart_item.product.price * cart_item.quantity
        quantity += cart_item.quantity

    if request.method == "POST":
        data = Order()
        data.user = current_user
        data.first_name = request.POST.get("first_name", "")
        data.last_name = request.POST.get("last_name", "")
        data.phone_number = request.POST.get("phone_number", "")
        data.email = request.POST.get("email", "")
        data.address_line_1 = request.POST.get("address_line_1", "")
        data.address_line_2 = request.POST.get("address_line_2", "")
        data.city = request.POST.get("city", "")
        data.order_note = request.POST.get("order_note", "")
        data.ip = request.META.get("REMOTE_ADDR")
        data.save()
        data.order_total = total
        data.save()

        # Generate a merchant-side order number used as transaction_uuid.
        yr = int(datetime.date.today().strftime("%Y"))
        dt = int(datetime.date.today().strftime("%d"))
        mt = int(datetime.date.today().strftime("%m"))
        d = datetime.date(yr, mt, dt)
        current_date = d.strftime("%Y%m%d")
        import uuid
        order_number = f"{current_date}{data.id}-{uuid.uuid4().hex[:6]}"
        data.order_number = order_number
        data.save()

        return redirect(reverse("esewarequest") + "?o_id=" + str(data.id))

    form = OrderForm()
    return redirect("home")


def order_complete(request):
    orders = Order.objects.filter(user=request.user, is_ordered=True).order_by("created_at")
    context = {"orders": orders}
    return render(request, "orders/order_complete.html", context)


class EsewaRequestView(View):
    def get(self, request, *args, **kwargs):
        from django_esewa import EsewaPayment

        o_id = request.GET.get("o_id")
        order = Order.objects.get(id=o_id)

        success_url = request.build_absolute_uri(reverse("esewaverify"))
        failure_url = request.build_absolute_uri(reverse("checkout"))

        total_amount = str(int(float(order.order_total)))
        transaction_uuid = str(order.order_number)

        esewa_pay = EsewaPayment(
            product_code=settings.ESEWA_PRODUCT_CODE,
            success_url=success_url,
            failure_url=failure_url,
            secret_key=settings.ESEWA_SECRET_KEY,
            amount=total_amount,
            tax_amount="0",
            total_amount=total_amount,
            product_service_charge="0",
            product_delivery_charge="0",
            transaction_uuid=transaction_uuid
        )
        signature = esewa_pay.create_signature()

        context = {
            "order": order,
            "esewa_payment_url": settings.ESEWA_PAYMENT_URL,
            "esewa_product_code": esewa_pay.product_code,
            "esewa_success_url": esewa_pay.success_url,
            "esewa_failure_url": esewa_pay.failure_url,
            "esewa_amount": esewa_pay.amount,
            "esewa_tax_amount": esewa_pay.tax_amount,
            "esewa_service_charge": esewa_pay.product_service_charge,
            "esewa_delivery_charge": esewa_pay.product_delivery_charge,
            "esewa_total_amount": esewa_pay.total_amount,
            "esewa_transaction_uuid": esewa_pay.transaction_uuid,
            "esewa_signed_field_names": "total_amount,transaction_uuid,product_code",
            "esewa_signature": signature,
        }
        return render(request, "esewarequest.html", context)


class EsewaVerifyView(View):
    def get(self, request, *args, **kwargs):
        encoded_data = request.GET.get("data")
        if not encoded_data:
            messages.warning(request, "Invalid payment response. Please try again.")
            return redirect("cart")

        try:
            # decode using base64 helper
            response_body_json = base64.b64decode(encoded_data).decode("utf-8")
            response_data = json.loads(response_body_json)
        except Exception:
            messages.warning(request, "Unable to decode payment response.")
            return redirect("cart")

        signed_field_names = response_data.get("signed_field_names", "")
        response_signature = response_data.get("signature", "")
        transaction_uuid = response_data.get("transaction_uuid", "")
        total_amount = response_data.get("total_amount", "")
        product_code = response_data.get("product_code", "")
        response_status = response_data.get("status", "")

        if not all([signed_field_names, response_signature, transaction_uuid, total_amount, product_code]):
            messages.warning(request, "Incomplete payment response from eSewa.")
            return redirect("cart")

        if product_code != settings.ESEWA_PRODUCT_CODE:
            messages.warning(request, "Invalid product code in payment response.")
            return redirect("cart")

        # Verify signature manually (django_esewa's verify_signature has a bug:
        # it compares response signature with request signature, but eSewa's
        # response uses different signed fields, so the comparison always fails)
        try:
            response_body_json = base64.b64decode(encoded_data).decode("utf-8")
            verify_data = json.loads(response_body_json)
            signed_field_names = verify_data.get("signed_field_names", "")
            received_signature = verify_data.get("signature", "")
            field_names = signed_field_names.split(",")
            message = ",".join(
                f"{field_name}={verify_data[field_name]}" for field_name in field_names
            )
            secret = settings.ESEWA_SECRET_KEY.encode("utf-8")
            message_bytes = message.encode("utf-8")
            hmac_sha256 = hmac.new(secret, message_bytes, hashlib.sha256)
            digest = hmac_sha256.digest()
            expected_signature = base64.b64encode(digest).decode("utf-8")
            is_valid = received_signature == expected_signature
        except Exception:
            is_valid = False

        if not is_valid:
            messages.warning(request, "Invalid payment signature. Please try again.")
            return redirect("cart")

        if response_status != "COMPLETE":
            messages.warning(request, "Payment was not completed.")
            return redirect("cart")

        try:
            order_obj = Order.objects.get(order_number=transaction_uuid, is_ordered=False)
        except Order.DoesNotExist:
            messages.warning(request, "Order not found or already processed.")
            return redirect("cart")

        try:
            expected_amount = Decimal(str(order_obj.order_total))
            received_amount = Decimal(str(total_amount))
        except (InvalidOperation, TypeError, ValueError):
            order_obj.delete()
            messages.warning(request, "Invalid payment amount received. Please try again.")
            return redirect("cart")

        if expected_amount != received_amount:
            order_obj.delete()
            messages.warning(request, "Payment amount did not match the order total.")
            return redirect("cart")

        # Check transaction status on eSewa servers
        try:
            status_url = settings.ESEWA_STATUS_CHECK_URL
            status_response = requests.get(status_url, params={
                "product_code": settings.ESEWA_PRODUCT_CODE,
                "total_amount": total_amount,
                "transaction_uuid": transaction_uuid,
            })
            if status_response.status_code != 200:
                messages.warning(request, "Unable to verify payment status with eSewa.")
                return redirect("cart")
            status_data = status_response.json()
            status_completed = status_data.get("status") == "COMPLETE"
        except Exception:
            messages.warning(request, "Unable to verify payment status with eSewa.")
            return redirect("cart")

        if not status_completed:
            order_obj.delete()
            messages.warning(request, "Payment failed. Please try again.")
            return redirect("cart")

        user = order_obj.user
        if not user:
            order_obj.delete()
            messages.warning(request, "Order is missing a user. Please try again.")
            return redirect("cart")

        ref_id = response_data.get("transaction_code")
        with transaction.atomic():
            payment = Payment.objects.create(
                user=user,
                payment_id=ref_id or transaction_uuid,
                payment_method="Esewa",
                amount_paid=str(received_amount),
                status="COMPLETE",
            )
            order_obj.payment = payment
            order_obj.is_ordered = True
            order_obj.status = "Completed"
            order_obj.save()

            cart_items = CartItem.objects.filter(user=user)
            for item in cart_items:
                OrderProduct.objects.create(
                    order=order_obj,
                    user=user,
                    product=item.product,
                    quantity=item.quantity,
                    product_price=item.product.price,
                    ordered=True,
                )

                # Auto-decrement product stock quantity
                product = item.product
                product.stock = max(0, product.stock - item.quantity)
                product.save()

            cart_items.delete()

        return redirect("order_complete")


# ============================================================
# Delivery Personnel Views
# ============================================================
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.core.mail import send_mail


def delivery_required(view_func):
    """Decorator that ensures the user is a logged-in delivery person."""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if not request.user.is_delivery_person:
            return HttpResponseForbidden("Access denied. Delivery personnel only.")
        return view_func(request, *args, **kwargs)
    return wrapper


@delivery_required
def delivery_dashboard(request):
    """Show active and today's completed deliveries for the logged-in delivery person."""
    from django.utils import timezone
    today = timezone.now().date()

    active_orders = Order.objects.filter(
        delivery_person=request.user,
        delivery_status__in=['Assigned', 'Out for Delivery', 'OTP Sent']
    ).order_by('-created_at')

    completed_today = Order.objects.filter(
        delivery_person=request.user,
        delivery_status='Completed',
        update_at__date=today
    ).order_by('-update_at')

    total_delivered_count = Order.objects.filter(
        delivery_person=request.user,
        delivery_status='Completed'
    ).count()

    context = {
        'active_orders': active_orders,
        'completed_today': completed_today,
        'assigned_count': active_orders.filter(delivery_status='Assigned').count(),
        'out_count': active_orders.filter(delivery_status='Out for Delivery').count(),
        'completed_today_count': completed_today.count(),
        'total_delivered_count': total_delivered_count,
    }
    return render(request, 'orders/delivery_dashboard.html', context)


@delivery_required
def delivery_order_detail(request, order_id):
    """Show detailed view of a single delivery order."""
    order = Order.objects.get(id=order_id, delivery_person=request.user)
    order_items = OrderProduct.objects.filter(order=order)
    subtotal = sum(item.product_price * item.quantity for item in order_items)

    context = {
        'order': order,
        'order_items': order_items,
        'subtotal': subtotal,
    }
    return render(request, 'orders/delivery_order_detail.html', context)


@delivery_required
def start_delivery(request, order_id):
    """Mark order as Out for Delivery."""
    order = Order.objects.get(id=order_id, delivery_person=request.user)
    if order.delivery_status == 'Assigned':
        order.delivery_status = 'Out for Delivery'
        order.save()
        messages.success(request, f'Delivery for Order #{order.order_number} started!')
    return redirect('delivery_dashboard')


@delivery_required
def send_delivery_otp(request, order_id):
    """Generate OTP, email it to the customer, and redirect to verification page with 2-minute rate limit."""
    order = Order.objects.get(id=order_id, delivery_person=request.user)

    # Rate limiting: Enforce 2-minute (120s) cooldown before resending delivery OTP
    now_ts = timezone.now().timestamp()
    if order.otp_created_at:
        elapsed = now_ts - order.otp_created_at.timestamp()
        if elapsed < 120:
            remaining = int(120 - elapsed)
            messages.warning(request, f'Please wait {remaining} seconds before sending another OTP to the customer.')
            return redirect('verify_delivery_otp', order_id=order.id)

    otp_code = order.generate_delivery_otp()
    order.delivery_status = 'OTP Sent'
    order.save()

    # Send OTP email to customer
    subject = f'GurungStore - Delivery Verification OTP for Order #{order.order_number}'
    message = (
        f'Dear {order.full_name()},\n\n'
        f'Your delivery person has arrived. Please share the following OTP code '
        f'with the delivery person to verify and complete your order:\n\n'
        f'    OTP Code: {otp_code}\n\n'
        f'This code is valid for 15 minutes.\n\n'
        f'Order #: {order.order_number}\n'
        f'Total: Rs. {order.order_total}\n\n'
        f'Thank you for shopping with GurungStore!'
    )
    send_mail(
        subject,
        message,
        None,  # Uses DEFAULT_FROM_EMAIL from settings
        [order.email],
        fail_silently=False,
    )

    messages.success(request, f'OTP has been sent to {order.email}')
    return redirect('verify_delivery_otp', order_id=order.id)


@delivery_required
def verify_delivery_otp(request, order_id):
    """Display OTP form and handle verification on POST."""
    order = Order.objects.get(id=order_id, delivery_person=request.user)

    if request.method == 'POST':
        input_otp = request.POST.get('otp', '').strip()

        if order.verify_delivery_otp(input_otp):
            order.delivery_status = 'Completed'
            order.status = 'Completed'
            order.delivery_otp = None
            order.otp_created_at = None
            order.save()
            messages.success(request, f'Order #{order.order_number} delivery verified and completed!')
            return redirect('delivery_dashboard')
        else:
            messages.error(request, 'Invalid or expired OTP. Please try again.')

    # Calculate 2-minute cooldown remaining for resend OTP (120 seconds)
    now_ts = timezone.now().timestamp()
    cooldown_remaining = 0
    if order.otp_created_at:
        elapsed = now_ts - order.otp_created_at.timestamp()
        cooldown_remaining = max(0, int(120 - elapsed))

    context = {
        'order': order,
        'cooldown_remaining': cooldown_remaining,
    }
    return render(request, 'orders/verify_otp.html', context)


@delivery_required
def delivery_history(request):
    """Show archive of all completed deliveries for this delivery person."""
    completed_orders = Order.objects.filter(
        delivery_person=request.user,
        delivery_status='Completed'
    ).order_by('-update_at')

    context = {
        'completed_orders': completed_orders,
    }
    return render(request, 'orders/delivery_history.html', context)


@delivery_required
def delivery_profile(request):
    """Profile management page for delivery personnel."""
    from app.models import UserProfile
    userprofile, _ = UserProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        phone_number = request.POST.get('phone_number', '').strip()
        city = request.POST.get('city', '').strip()

        if first_name:
            request.user.first_name = first_name
        if last_name:
            request.user.last_name = last_name
        if phone_number:
            request.user.phone_number = phone_number
        request.user.save()

        userprofile.city = city
        if 'profile_pic' in request.FILES:
            userprofile.profile_pic = request.FILES['profile_pic']
        userprofile.save()

        messages.success(request, 'Your delivery profile has been updated successfully!')
        return redirect('delivery_profile')

    completed_count = Order.objects.filter(
        delivery_person=request.user,
        delivery_status='Completed'
    ).count()

    context = {
        'userprofile': userprofile,
        'completed_count': completed_count,
    }
    return render(request, 'orders/delivery_profile.html', context)


# ============================================================
# Delivery Personnel Authentication Views
# ============================================================
def delivery_login(request):
    """Separate login view for Delivery Personnel."""
    if request.user.is_authenticated:
        if getattr(request.user, 'is_delivery_person', False):
            return redirect('delivery_dashboard')
        else:
            return redirect('home')

    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '').strip()

        user = auth.authenticate(email=email, password=password)

        if user is not None:
            if getattr(user, 'is_delivery_person', False):
                auth.login(request, user)
                messages.success(request, 'Welcome to the Delivery Portal!')
                return redirect('delivery_dashboard')
            else:
                messages.error(request, 'Access denied. This portal is for Delivery Personnel only. Please use Customer Login.')
        else:
            messages.error(request, 'Invalid email address or password.')

    return render(request, 'orders/delivery_login.html')



