from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages, auth
from django.http import HttpResponseForbidden
from django.db.models import Sum, Count, Q, FloatField, Avg
from django.db.models.functions import Cast
from django.utils import timezone
from functools import wraps

from app.models import Account
from orders.models import Order, Payment, OrderProduct
from store.models import Product, ReviewRating
from category.models import Category


# ──────────────────────────────────────────────
# Access Control Decorator
# ──────────────────────────────────────────────

def admin_required(view_func):
    """Decorator that restricts access to admin users only."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('admin_login')
        if not (request.user.is_admin or request.user.is_superadmin):
            return HttpResponseForbidden('Access denied. Store Administrators only.')
        return view_func(request, *args, **kwargs)
    return wrapper


# ──────────────────────────────────────────────
# Admin Authentication
# ──────────────────────────────────────────────

def admin_login(request):
    """Dedicated login page for Store Administrators."""
    if request.user.is_authenticated:
        if request.user.is_admin or request.user.is_superadmin:
            return redirect('admin_dashboard')

    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        print(f"[ADMIN LOGIN] Attempt: email={email}")

        user = auth.authenticate(email=email, password=password)
        print(f"[ADMIN LOGIN] Auth result: {user}")

        if user is not None:
            if user.is_admin or user.is_superadmin:
                auth.login(request, user)
                print(f"[ADMIN LOGIN] Login successful for {user.email}")
                messages.success(request, f'Welcome back, {user.first_name}!')
                return redirect('admin_dashboard')
            else:
                messages.error(request, 'Access denied. This portal is reserved for Store Administrators only.')
        else:
            messages.error(request, 'Invalid email or password.')

    return render(request, 'store_admin/admin_login.html')


def admin_logout(request):
    """Log out the admin and redirect to admin login."""
    auth.logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('admin_login')


# ──────────────────────────────────────────────
# Executive Dashboard
# ──────────────────────────────────────────────

@admin_required
def admin_dashboard(request):
    """Executive dashboard with KPI metrics, sales chart data, and recent orders."""
    today = timezone.now().date()

    # KPI metrics
    total_orders = Order.objects.filter(is_ordered=True).count()
    total_revenue = Order.objects.filter(is_ordered=True).aggregate(
        total=Sum(Cast('order_total', FloatField()))
    )['total'] or 0
    pending_deliveries = Order.objects.filter(
        is_ordered=True,
        delivery_status__in=['Pending', 'Assigned', 'Out for Delivery', 'OTP Sent']
    ).count()
    total_customers = Account.objects.filter(
        is_admin=False, is_superadmin=False, is_delivery_person=False, is_active=True
    ).count()
    total_products = Product.objects.count()
    orders_today = Order.objects.filter(is_ordered=True, created_at__date=today).count()

    # Recent 10 orders
    recent_orders = Order.objects.filter(is_ordered=True).order_by('-created_at')[:10]

    # Sales data for last 7 days (for Chart.js)
    sales_labels = []
    sales_data = []
    for i in range(6, -1, -1):
        day = today - timezone.timedelta(days=i)
        sales_labels.append(day.strftime('%b %d'))
        day_total = Order.objects.filter(
            is_ordered=True, created_at__date=day
        ).aggregate(total=Sum(Cast('order_total', FloatField())))['total'] or 0
        sales_data.append(float(day_total))

    context = {
        'total_orders': total_orders,
        'total_revenue': total_revenue,
        'pending_deliveries': pending_deliveries,
        'total_customers': total_customers,
        'total_products': total_products,
        'orders_today': orders_today,
        'recent_orders': recent_orders,
        'sales_labels': sales_labels,
        'sales_data': sales_data,
    }
    return render(request, 'store_admin/admin_dashboard.html', context)


# ──────────────────────────────────────────────
# Order Dispatch Center
# ──────────────────────────────────────────────

@admin_required
def admin_orders(request):
    """Order management with status filtering and delivery assignment."""
    status_filter = request.GET.get('status', 'all')
    delivery_filter = request.GET.get('delivery', 'all')

    orders = Order.objects.filter(is_ordered=True).order_by('-created_at')

    if status_filter != 'all':
        orders = orders.filter(status=status_filter)
    if delivery_filter != 'all':
        orders = orders.filter(delivery_status=delivery_filter)

    delivery_agents = Account.objects.filter(is_delivery_person=True, is_active=True)

    context = {
        'orders': orders,
        'delivery_agents': delivery_agents,
        'status_filter': status_filter,
        'delivery_filter': delivery_filter,
    }
    return render(request, 'store_admin/admin_orders.html', context)


@admin_required
def admin_order_detail(request, order_id):
    """Admin view to inspect comprehensive order details matching customer invoice."""
    order = get_object_or_404(Order, id=order_id)
    order_items = OrderProduct.objects.filter(order=order)

    subtotal = 0
    for item in order_items:
        subtotal += item.product_price * item.quantity

    delivery_agents = Account.objects.filter(is_delivery_person=True, is_active=True)

    context = {
        'order': order,
        'order_items': order_items,
        'subtotal': subtotal,
        'delivery_agents': delivery_agents,
    }
    return render(request, 'store_admin/admin_order_detail.html', context)


@admin_required
def assign_delivery(request, order_id):
    """Assign a delivery person to an order via POST."""
    if request.method == 'POST':
        order = get_object_or_404(Order, id=order_id)

        if order.delivery_status == 'Completed':
            messages.error(request, f'Order #{order.order_number} has already been delivered and cannot be reassigned.')
            return redirect('admin_orders')

        agent_id = request.POST.get('delivery_person')

        if agent_id:
            agent = get_object_or_404(Account, id=agent_id, is_delivery_person=True)
            order.delivery_person = agent
            order.delivery_status = 'Assigned'
            order.save()
            messages.success(request, f'Order #{order.order_number} assigned to {agent.first_name} {agent.last_name}.')
        else:
            order.delivery_person = None
            order.delivery_status = 'Pending'
            order.save()
            messages.info(request, f'Delivery assignment removed for Order #{order.order_number}.')

    return redirect('admin_orders')


# ──────────────────────────────────────────────
# Product & Inventory Management
# ──────────────────────────────────────────────

@admin_required
def admin_products(request):
    """Product inventory manager with low-stock alerts."""
    products = Product.objects.all().order_by('-created_date')
    categories = Category.objects.all().order_by('category_name')
    low_stock_count = Product.objects.filter(stock__gt=0, stock__lt=5).count()
    out_of_stock_count = Product.objects.filter(stock=0).count()

    context = {
        'products': products,
        'categories': categories,
        'low_stock_count': low_stock_count,
        'out_of_stock_count': out_of_stock_count,
    }
    return render(request, 'store_admin/admin_products.html', context)


@admin_required
def admin_add_product(request):
    """Add a new product from the Store Admin page with 500 KB image validation and numerical stock."""
    if request.method == 'POST':
        product_name = request.POST.get('product_name', '').strip()
        category_id = request.POST.get('category')
        price = request.POST.get('price')
        stock = request.POST.get('stock', '10')
        description = request.POST.get('description', '').strip()
        image = request.FILES.get('image')

        if not product_name or not category_id or not price:
            messages.error(request, 'Please fill in all required fields (Product Name, Category, Price).')
            return redirect('admin_products')

        try:
            stock_qty = max(0, int(stock))
        except ValueError:
            stock_qty = 10

        # Image File Size Validation (Max 500 KB)
        if image:
            if image.size > 500 * 1024:
                file_size_kb = round(image.size / 1024, 1)
                messages.error(
                    request,
                    f'Image file size ({file_size_kb} KB) exceeds the maximum allowed limit of 500 KB. Please compress or choose a smaller image.'
                )
                return redirect('admin_products')

        try:
            category = Category.objects.get(id=category_id)
            product = Product(
                product_name=product_name,
                category=category,
                price=int(price),
                stock=stock_qty,
                description=description,
            )
            if image:
                product.image = image
            product.save()

            messages.success(request, f'Product "{product_name}" added successfully with {product.stock} units in stock!')
        except Exception as e:
            messages.error(request, f'Error adding product: {str(e)}')

    return redirect('admin_products')


@admin_required
def admin_edit_product(request, product_id):
    """Edit an existing product with 500 KB image validation and stock management."""
    product = get_object_or_404(Product, id=product_id)
    if request.method == 'POST':
        product_name = request.POST.get('product_name', '').strip()
        category_id = request.POST.get('category')
        price = request.POST.get('price')
        stock = request.POST.get('stock', '0')
        description = request.POST.get('description', '').strip()
        image = request.FILES.get('image')

        if not product_name or not category_id or not price:
            messages.error(request, 'Please fill in all required fields (Product Name, Category, Price).')
            return redirect('admin_products')

        try:
            stock_qty = max(0, int(stock))
        except ValueError:
            stock_qty = 0

        if image and image.size > 500 * 1024:
            file_size_kb = round(image.size / 1024, 1)
            messages.error(
                request,
                f'Image file size ({file_size_kb} KB) exceeds the maximum allowed limit of 500 KB. Please compress or choose a smaller image.'
            )
            return redirect('admin_products')

        try:
            category = Category.objects.get(id=category_id)
            product.product_name = product_name
            product.category = category
            product.price = int(price)
            product.stock = stock_qty
            product.description = description
            if image:
                product.image = image
            from django.template.defaultfilters import slugify
            product.slug = slugify(product_name)
            product.save()

            messages.success(request, f'Product "{product_name}" updated successfully (Stock: {product.stock})!')
        except Exception as e:
            messages.error(request, f'Error updating product: {str(e)}')

    return redirect('admin_products')


@admin_required
def admin_delete_product(request, product_id):
    """Delete a product from the database."""
    product = get_object_or_404(Product, id=product_id)
    if request.method == 'POST':
        name = product.product_name
        product.delete()
        messages.success(request, f'Product "{name}" deleted successfully.')

    return redirect('admin_products')


@admin_required
def admin_bulk_stock_toggle(request):
    """Bulk mark checked products as In Stock or Out of Stock, or update stock values."""
    if request.method == 'POST':
        action = request.POST.get('action')
        product_ids = request.POST.getlist('product_ids')

        if not product_ids:
            messages.warning(request, 'No products selected for bulk action.')
            return redirect('admin_products')

        products = Product.objects.filter(id__in=product_ids)
        updated_count = 0

        if action == 'in_stock':
            for product in products:
                if product.stock <= 0:
                    product.stock = 10  # Default stock quantity when marking in stock
                product.save()
                updated_count += 1
            messages.success(request, f'Marked {updated_count} product(s) as In Stock.')

        elif action == 'out_of_stock':
            for product in products:
                product.stock = 0
                product.save()
                updated_count += 1
            messages.success(request, f'Marked {updated_count} product(s) as Out of Stock.')

        elif action == 'update_stock':
            new_stock = request.POST.get('bulk_stock_value', '10')
            try:
                new_stock_val = max(0, int(new_stock))
                for product in products:
                    product.stock = new_stock_val
                    product.save()
                    updated_count += 1
                messages.success(request, f'Updated stock quantity to {new_stock_val} for {updated_count} product(s).')
            except ValueError:
                messages.error(request, 'Invalid stock quantity entered.')

    return redirect('admin_products')


# ──────────────────────────────────────────────
# Category Management (CRUD)
# ──────────────────────────────────────────────

@admin_required
def admin_categories(request):
    """Category manager listing all categories with product counts."""
    categories = Category.objects.annotate(product_count=Count('product')).order_by('category_name')

    context = {
        'categories': categories,
    }
    return render(request, 'store_admin/admin_categories.html', context)


@admin_required
def admin_add_category(request):
    """Add a new category."""
    if request.method == 'POST':
        category_name = request.POST.get('category_name', '').strip()
        icon = request.POST.get('icon', '').strip() or 'ci-grid'

        if not category_name:
            messages.error(request, 'Category name is required.')
            return redirect('admin_categories')

        if Category.objects.filter(category_name__iexact=category_name).exists():
            messages.error(request, f'Category "{category_name}" already exists.')
            return redirect('admin_categories')

        try:
            category = Category(
                category_name=category_name,
                icon=icon
            )
            category.save()
            messages.success(request, f'Category "{category_name}" created successfully!')
        except Exception as e:
            messages.error(request, f'Error creating category: {str(e)}')

    return redirect('admin_categories')


@admin_required
def admin_edit_category(request, category_id):
    """Edit an existing category."""
    category = get_object_or_404(Category, id=category_id)
    if request.method == 'POST':
        category_name = request.POST.get('category_name', '').strip()
        icon = request.POST.get('icon', '').strip() or 'ci-grid'

        if not category_name:
            messages.error(request, 'Category name cannot be empty.')
            return redirect('admin_categories')

        if Category.objects.filter(category_name__iexact=category_name).exclude(id=category_id).exists():
            messages.error(request, f'Category name "{category_name}" is already taken.')
            return redirect('admin_categories')

        try:
            from django.template.defaultfilters import slugify
            category.category_name = category_name
            category.icon = icon
            category.slug = slugify(category_name)
            category.save()
            messages.success(request, f'Category "{category_name}" updated successfully!')
        except Exception as e:
            messages.error(request, f'Error updating category: {str(e)}')

    return redirect('admin_categories')


@admin_required
def admin_delete_category(request, category_id):
    """Delete a category."""
    category = get_object_or_404(Category, id=category_id)
    if request.method == 'POST':
        product_count = Product.objects.filter(category=category).count()
        if product_count > 0:
            messages.error(
                request,
                f'Cannot delete category "{category.category_name}" because it has {product_count} product(s) attached to it.'
            )
            return redirect('admin_categories')

        name = category.category_name
        category.delete()
        messages.success(request, f'Category "{name}" deleted successfully.')

    return redirect('admin_categories')


# ──────────────────────────────────────────────
# Delivery Team Directory
# ──────────────────────────────────────────────

@admin_required
def admin_delivery_team(request):
    """Delivery agent roster with performance metrics."""
    agents = Account.objects.filter(is_delivery_person=True).order_by('first_name')

    agent_data = []
    for agent in agents:
        active_count = Order.objects.filter(
            delivery_person=agent,
            delivery_status__in=['Assigned', 'Out for Delivery', 'OTP Sent']
        ).count()
        completed_count = Order.objects.filter(
            delivery_person=agent,
            delivery_status='Completed'
        ).count()
        agent_data.append({
            'agent': agent,
            'active_count': active_count,
            'completed_count': completed_count,
        })

    context = {
        'agent_data': agent_data,
    }
    return render(request, 'store_admin/admin_delivery_team.html', context)


@admin_required
def admin_add_delivery_agent(request):
    """Create a new delivery agent from the Store Admin portal."""
    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip().lower()
        phone_number = request.POST.get('phone_number', '').strip()
        password = request.POST.get('password', '')

        if not first_name or not last_name or not email or not password:
            messages.error(request, 'Please fill in all required fields (First Name, Last Name, Email, Password).')
            return redirect('admin_delivery_team')

        if Account.objects.filter(email=email).exists():
            messages.error(request, f'An account with email "{email}" already exists.')
            return redirect('admin_delivery_team')

        try:
            base_username = email.split('@')[0]
            username = base_username
            counter = 1
            while Account.objects.filter(username=username).exists():
                username = f"{base_username}{counter}"
                counter += 1

            user = Account.objects.create_user(
                first_name=first_name,
                last_name=last_name,
                username=username,
                email=email,
                password=password
            )
            user.phone_number = phone_number
            user.is_delivery_person = True
            user.is_active = True
            user.save()

            messages.success(request, f'Delivery agent "{first_name} {last_name}" created successfully!')
        except Exception as e:
            messages.error(request, f'Error creating delivery agent: {str(e)}')

    return redirect('admin_delivery_team')


# ──────────────────────────────────────────────
# User Management
# ──────────────────────────────────────────────

@admin_required
def admin_users(request):
    """User directory with role and status management."""
    search_q = request.GET.get('q', '').strip()
    role_filter = request.GET.get('role', 'all')

    users = Account.objects.all().order_by('-date_joined')

    if search_q:
        users = users.filter(
            Q(first_name__icontains=search_q) |
            Q(last_name__icontains=search_q) |
            Q(email__icontains=search_q) |
            Q(phone_number__icontains=search_q)
        )

    if role_filter == 'customer':
        users = users.filter(is_admin=False, is_superadmin=False, is_delivery_person=False)
    elif role_filter == 'delivery':
        users = users.filter(is_delivery_person=True)
    elif role_filter == 'admin':
        users = users.filter(Q(is_admin=True) | Q(is_superadmin=True))

    context = {
        'users': users,
        'search_q': search_q,
        'role_filter': role_filter,
    }
    return render(request, 'store_admin/admin_users.html', context)


@admin_required
def toggle_user_active(request, user_id):
    """Toggle a user's is_active status."""
    user = get_object_or_404(Account, id=user_id)
    # Prevent admin from deactivating themselves
    if user == request.user:
        messages.error(request, 'You cannot deactivate your own account.')
        return redirect('admin_users')

    user.is_active = not user.is_active
    user.save()
    status_text = 'activated' if user.is_active else 'blocked'
    messages.success(request, f'{user.first_name} {user.last_name} has been {status_text}.')
    return redirect('admin_users')


@admin_required
def toggle_user_delivery(request, user_id):
    """Toggle a user's is_delivery_person role."""
    user = get_object_or_404(Account, id=user_id)
    user.is_delivery_person = not user.is_delivery_person
    user.save()
    role_text = 'promoted to Delivery Agent' if user.is_delivery_person else 'demoted to Customer'
    messages.success(request, f'{user.first_name} {user.last_name} has been {role_text}.')
    return redirect('admin_users')


@admin_required
def admin_delete_user(request, user_id):
    """Safely delete a user account from store admin."""
    user_to_delete = get_object_or_404(Account, id=user_id)

    # Prevent admin from deleting their own account
    if user_to_delete == request.user:
        messages.error(request, 'You cannot delete your own logged-in admin account.')
        return redirect('admin_users')

    # Prevent deleting superadmin accounts unless requester is a superadmin
    if user_to_delete.is_superadmin and not request.user.is_superadmin:
        messages.error(request, 'Only superadmins can delete superadmin accounts.')
        return redirect('admin_users')

    user_name = f"{user_to_delete.first_name} {user_to_delete.last_name} ({user_to_delete.email})"
    user_to_delete.delete()
    messages.success(request, f'User account "{user_name}" has been deleted successfully.')
    return redirect('admin_users')


# ──────────────────────────────────────────────
# eSewa Transaction Audit Log
# ──────────────────────────────────────────────

@admin_required
def admin_transactions(request):
    """eSewa payment transaction log."""
    transactions = Payment.objects.all().order_by('-created_at')

    context = {
        'transactions': transactions,
    }
    return render(request, 'store_admin/admin_transactions.html', context)


# ──────────────────────────────────────────────
# Customer Review Moderation
# ──────────────────────────────────────────────

@admin_required
def admin_reviews(request):
    """Customer Review & Rating Moderation Manager."""
    status_filter = request.GET.get('status', 'all')
    search_q = request.GET.get('q', '').strip()

    reviews = ReviewRating.objects.select_related('product', 'user').order_by('-created_at')

    if status_filter == 'approved':
        reviews = reviews.filter(status=True)
    elif status_filter == 'hidden':
        reviews = reviews.filter(status=False)

    if search_q:
        reviews = reviews.filter(
            Q(subject__icontains=search_q) |
            Q(review__icontains=search_q) |
            Q(product__product_name__icontains=search_q) |
            Q(user__first_name__icontains=search_q) |
            Q(user__email__icontains=search_q)
        )

    total_reviews = ReviewRating.objects.count()
    approved_count = ReviewRating.objects.filter(status=True).count()
    hidden_count = ReviewRating.objects.filter(status=False).count()
    avg_rating = ReviewRating.objects.filter(status=True).aggregate(avg=Avg('rating'))['avg'] or 0.0

    context = {
        'reviews': reviews,
        'status_filter': status_filter,
        'search_q': search_q,
        'total_reviews': total_reviews,
        'approved_count': approved_count,
        'hidden_count': hidden_count,
        'avg_rating': round(avg_rating, 1),
    }
    return render(request, 'store_admin/admin_reviews.html', context)


@admin_required
def toggle_review_status(request, review_id):
    """Approve or Hide a customer review."""
    review = get_object_or_404(ReviewRating, id=review_id)
    review.status = not review.status
    review.save()

    status_str = "Approved (Visible)" if review.status else "Hidden (Unapproved)"
    messages.success(request, f'Review for "{review.product.product_name}" is now {status_str}.')
    return redirect('admin_reviews')


@admin_required
def admin_delete_review(request, review_id):
    """Delete a customer review permanently."""
    review = get_object_or_404(ReviewRating, id=review_id)
    if request.method == 'POST':
        prod_name = review.product.product_name
        review.delete()
        messages.success(request, f'Review for "{prod_name}" has been permanently deleted.')

    return redirect('admin_reviews')
