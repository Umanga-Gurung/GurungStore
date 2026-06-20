from django.shortcuts import render, get_object_or_404, redirect
from store.models import Product, ReviewRating
from category.models import Category
from .forms import ReviewForms
from django.contrib import messages

 
from django.contrib.auth.decorators import login_required

from django.db.models import Q

def store(request, category_slug=None):
    categories = None
    products = None
    products_count = 0
    query = request.GET.get('q', None)
    category_query = request.GET.get('category', None)

    if category_slug is not None:
        categories = get_object_or_404(Category, slug=category_slug)
        products = Product.objects.filter(category=categories, is_available=True)
        products_count = products.count()
    elif category_query and category_query != "" and category_query != "All Category":
        try:
            categories = Category.objects.get(category_name=category_query)
            products = Product.objects.filter(category=categories, is_available=True)
            products_count = products.count()
        except Category.DoesNotExist:
            products = Product.objects.none()
            products_count = 0
    elif query:
        products = Product.objects.filter(
            Q(product_name__icontains=query) | Q(description__icontains=query),
            is_available=True
        )
        products_count = products.count()
    else:
        products = Product.objects.filter(is_available=True)
        products_count = products.count()

    context = {
        'products': products,
        'products_count': products_count,
        'categories': categories,
    }
    return render(request, 'store/store.html', context)


@login_required(login_url='login')
def submit_reviews(request, product_id):
    url = request.META.get('HTTP_REFERER')
    if request.method == 'POST':
        try:
            reviews = ReviewRating.objects.get(user__id=request.user.id, product__id=product_id)
            form = ReviewForms(request.POST, instance=reviews)
            if form.is_valid():
                form.save()
                messages.success(request, 'Thank you, your Review has been updated')
            else:
                messages.error(request, 'Invalid rating or review input.')
            return redirect(url)

        except ReviewRating.DoesNotExist:
            form = ReviewForms(request.POST)
            if form.is_valid():
                data = ReviewRating()
                data.subject = form.cleaned_data['subject']
                data.rating = form.cleaned_data['rating']
                data.review = form.cleaned_data['review']
                data.ip = request.META.get('REMOTE_ADDR')
                data.product_id = product_id
                data.user_id = request.user.id
                data.save()
                messages.success(request, 'Thank you, your Review has been submitted')
            else:
                messages.error(request, 'Invalid rating or review input.')
            return redirect(url)
    return redirect('home')

