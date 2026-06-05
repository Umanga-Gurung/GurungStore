from django.shortcuts import render, redirect,get_object_or_404
from .forms import RegistrationForm, UserForm, UserProfileForm
from app.models import Account, UserProfile
from orders.models import Order, OrderProduct
from cart.models import Cart, CartItem
from cart.views import _cart_id
import requests
from django.http import HttpResponse
from django.contrib import messages, auth
from django.contrib.auth.decorators import login_required
# Create your views here.
"""verification email"""
from django.contrib.sites.shortcuts import get_current_site
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import EmailMessage

import random
from django.utils import timezone
from django.core.mail import send_mail


def register(request):
    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            first_name = form.cleaned_data['first_name']
            last_name = form.cleaned_data['last_name']
            email = form.cleaned_data['email'].strip().lower()
            phone_number = form.cleaned_data['phone_number']
            password = form.cleaned_data['password']

            # Check if an ALREADY VERIFIED active account exists with this email
            if Account.objects.filter(email=email, is_active=True).exists():
                messages.error(request, 'An active account with this email address already exists. Please log in.')
                return redirect('register')

            # Generate 6-Digit Email Verification OTP
            otp_code = str(random.randint(100000, 999999))

            # Store pending registration in session (NOT in DB yet!)
            request.session['reg_user_data'] = {
                'first_name': first_name,
                'last_name': last_name,
                'email': email,
                'phone_number': phone_number,
                'password': password,
            }
            request.session['reg_otp'] = otp_code
            request.session['reg_otp_time'] = timezone.now().timestamp()

            # Send Email OTP
            subject = 'GurungStore - Account Verification OTP'
            message = (
                f'Dear {first_name},\n\n'
                f'Thank you for registering with GurungStore!\n\n'
                f'Your 6-digit email verification OTP code is:\n\n'
                f'    {otp_code}\n\n'
                f'This code is valid for 15 minutes. Enter this code to complete your registration.\n\n'
                f'Best regards,\nGurungStore Team'
            )
            send_mail(subject, message, None, [email], fail_silently=False)

            messages.success(request, f'Registration initiated! We have sent a 6-digit OTP to {email}.')
            return redirect('verify_email_otp')
    else:
        form = RegistrationForm()        
    
    context = {
        'form': form
    }
    return render(request, 'accounts/register.html', context)


def verify_email_otp(request):
    """View to verify registration OTP and ONLY create user in DB upon successful OTP match."""
    reg_data = request.session.get('reg_user_data')
    session_otp = request.session.get('reg_otp')
    otp_time = request.session.get('reg_otp_time')

    if not reg_data or not session_otp:
        messages.error(request, 'No pending registration found. Please register.')
        return redirect('register')

    email = reg_data.get('email')

    if request.method == 'POST':
        input_otp = request.POST.get('otp', '').strip()

        # Check 15-minute expiry (900 seconds)
        elapsed = timezone.now().timestamp() - (otp_time or 0)
        if elapsed > 900:
            messages.error(request, 'OTP code has expired. Click Resend OTP to receive a new code.')
            return redirect('verify_email_otp')

        if input_otp == str(session_otp):
            # Clean up any stale unverified account if present
            Account.objects.filter(email=email, is_active=False).delete()

            # SAVE USER TO DATABASE ONLY NOW!
            first_name = reg_data['first_name']
            last_name = reg_data['last_name']
            username = email.split('@')[0]
            phone_number = reg_data['phone_number']
            password = reg_data['password']

            user = Account.objects.create_user(
                first_name=first_name,
                last_name=last_name,
                username=username,
                email=email,
                password=password
            )
            user.phone_number = phone_number
            user.is_active = True
            user.save()

            # Create UserProfile
            profile, created = UserProfile.objects.get_or_create(user=user)
            profile.profile_pic = 'default/default-user.png'
            profile.save()

            # Clean up session registration keys
            request.session.pop('reg_user_data', None)
            request.session.pop('reg_otp', None)
            request.session.pop('reg_otp_time', None)

            messages.success(request, 'Account created and verified successfully! You can now log in.')
            return redirect('login')
        else:
            messages.error(request, 'Invalid OTP code. Please check your email and try again.')

    # Calculate 2-minute cooldown remaining for resend OTP (120 seconds)
    now_ts = timezone.now().timestamp()
    elapsed = now_ts - (otp_time or 0)
    cooldown_remaining = max(0, int(120 - elapsed))

    context = {
        'email': email,
        'cooldown_remaining': cooldown_remaining,
    }
    return render(request, 'accounts/verify_email_otp.html', context)


def resend_email_otp(request):
    """Resend a new 6-digit OTP code to the registering user with a 2-minute rate limit."""
    reg_data = request.session.get('reg_user_data')
    last_sent = request.session.get('reg_otp_time', 0)

    if not reg_data:
        messages.error(request, 'No pending registration found. Please register.')
        return redirect('register')

    email = reg_data.get('email')
    first_name = reg_data.get('first_name', 'Customer')

    # Rate limiting: Enforce 2-minute (120s) cooldown before resending OTP
    now_ts = timezone.now().timestamp()
    elapsed = now_ts - (last_sent or 0)
    if elapsed < 120:
        remaining = int(120 - elapsed)
        messages.warning(request, f'Please wait {remaining} seconds before requesting a new OTP.')
        return redirect('verify_email_otp')

    otp_code = str(random.randint(100000, 999999))
    request.session['reg_otp'] = otp_code
    request.session['reg_otp_time'] = timezone.now().timestamp()

    subject = 'GurungStore - Resent Account Verification OTP'
    message = (
        f'Dear {first_name},\n\n'
        f'Your new 6-digit email verification OTP is:\n\n'
        f'    {otp_code}\n\n'
        f'This code is valid for 15 minutes.\n\n'
        f'Best regards,\nGurungStore Team'
    )
    send_mail(subject, message, None, [email], fail_silently=False)

    messages.success(request, f'A new 6-digit OTP has been sent to {email}.')
    return redirect('verify_email_otp')



def login(request):
    if request.method == "POST":
        email = request.POST['email']
        password = request.POST['password']

        user = auth.authenticate(email=email, password=password)

        if user is not None:
            try:
                cart = Cart.objects.get(cart_id=_cart_id(request))
                is_cart_item_exists = CartItem.objects.filter(cart=cart).exists()
                if is_cart_item_exists:
                    cart_item = CartItem.objects.filter(cart=cart)

                    for item in cart_item:
                        item.user = user
                        item.save()


            except:
                pass    
            auth.login(request, user)
            messages.success(request, 'You are now logged in.')
            if getattr(user, 'is_delivery_person', False) and not getattr(user, 'is_admin', False):
                return redirect('delivery_dashboard')
            url = request.META.get('HTTP_REFERER')
            try:
                query = requests.utils.urlparse(url).query
                params = dict(x.split('=') for x in query.split('&'))
                if 'next' in params:
                    nextPage = params['next']
                    return redirect(nextPage)
                
            except:
                return redirect('dashbord')
                  
        else:
            if Account.objects.filter(email=email, is_active=False).exists():
                messages.error(request, 'Your account is not activated yet. Please check your email inbox to activate your account.')
            else:
                messages.error(request, 'Invalid login credentials.')
            return redirect('login')     
    return render(request, 'accounts/login.html')



@login_required(login_url='login')
def logout(request):
    auth.logout(request)
    
    return redirect('login')



def activate(request, uidb64, token):
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = Account._default_manager.get(pk=uid)
    except(TypeError, ValueError, OverflowError, Account.DoesNotExist):
        user = None
    if user is not None and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save()
        messages.success(request, 'Congratulations! Your account has been activated successfully. You can now log in.')
        return redirect('login')
    else:
        messages.error(request, 'Invalid or expired activation link.')
        return redirect('register')   
          
@login_required(login_url='login')
def dashbord(request):
    orders = Order.objects.order_by('created_at').filter(user_id=request.user.id, is_ordered=True)
    orders_count = orders.count()
    context ={
        'orders':orders,
        'orders_count': orders_count
    }
    return render(request, 'accounts/dashbord.html', context)



def forgotPassword(request):
    if request.method == "POST":
        email = request.POST['email']
        if Account.objects.filter(email=email).exists():
            user = Account.objects.get(email__exact=email)
            """reset password"""
            current_site = get_current_site(request)
            mail_subject = "Please reset your password"
            message = render_to_string('accounts/reset_password.html',{
                'user': user,
                'domain': current_site,
                'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                'token': default_token_generator.make_token(user)

            })
            to_email = email
            send_email = EmailMessage(mail_subject,message,to=[to_email])
            send_email.send()
            messages.success(request, 'password reset email has been sent')
            return redirect('login')

        else:
            messages.error(request, 'account dose not exists')
            return redirect('forgot-password')

    return render(request, 'accounts/forgotPassword.html')

def resetPassword_validate(request, uidb64,token):
     try:
         uid = urlsafe_base64_decode(uidb64).decode()
         user = Account._default_manager.get(pk=uid)
     except(TypeError, ValueError, OverflowError, Account.DoesNotExist):

         user = None
     if user is not None and default_token_generator.check_token(user, token):
         request.session['uid'] = uid
         messages.success(request, 'reset your password')
         return redirect('reset-password')
     else:
         messages.error(request, 'this link has expired')
         return redirect('login')         


def resetPassword(request):
    if request.method == 'POST':
        password = request.POST['password']
        confirm_password = request.POST['confirm_password']

        if password == confirm_password:
            uid = request.session.get('uid')
            user = Account.objects.get(pk=uid)
            user.set_password(password)
            user.save()
            messages.success(request, 'password has been reset')
            return redirect('login')

        else:
            messages.error(request,'password do not match')
            return redirect('reset-password')
    else:
      return render(request, 'accounts/resetPassword.html')
      
        
                 
def my_orders(request):
    orders = Order.objects.filter(user=request.user, is_ordered=True).order_by('created_at')
    context ={
        'orders':orders
    }
    return render(request, 'accounts/my_orders.html', context)



def edit_profile(request):
    userprofile = get_object_or_404(UserProfile, user=request.user)
    if request.method == 'POST':

        user_form = UserForm(request.POST, instance=request.user)
        profile_form = UserProfileForm(request.POST, request.FILES, instance=userprofile)

        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, f'your profile has been updated')
            return redirect('edit_profile')

    else:
       user_form =  UserForm(instance=request.user)
       profile_form = UserProfileForm(instance=userprofile)
       

    context ={
        'user_form': user_form,
        'profile_form':profile_form,
        'userprofile':userprofile
    }
    return render(request, 'accounts/edit_profile.html',context)

@login_required(login_url='login')
def order_detail(request, order_id):
    order_detail = OrderProduct.objects.filter(order__id=order_id)
    order = Order.objects.get(id=order_id)
    subtotal = 0
    for i in order_detail:
        subtotal += i.product_price * i.quantity

    context = {
        'order_detail':order_detail,
        'order' :order,
        'subtotal':subtotal,
    }
    return render(request, 'accounts/order_detail.html',context)
