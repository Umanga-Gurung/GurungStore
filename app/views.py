from django.shortcuts import render
from store.models import Product, ReviewRating, ProductGalary
from django.views.generic import  DetailView
from orders.models import OrderProduct
from django.http import JsonResponse
from django.core.cache import cache


def home(request):
    products = Product.objects.all().filter(is_available=True)
    context = {
        'products' : products,
    }
    return render(request, 'home.html',context)


class ProductDetailView(DetailView):
    model = Product

    def get_context_data(self,product_id=None, **kwargs):
        context = super(ProductDetailView,self).get_context_data(**kwargs)
        context['reviews'] = ReviewRating.objects.filter(product_id=self.object.id, status=True)
        # Smart "You may also like" related products logic
        same_category_products = list(Product.objects.filter(category=self.object.category, is_available=True).exclude(id=self.object.id)[:4])
        if len(same_category_products) < 4:
            needed = 4 - len(same_category_products)
            other_products = list(Product.objects.filter(is_available=True).exclude(id=self.object.id).exclude(category=self.object.category)[:needed])
            context['all_products'] = same_category_products + other_products
        else:
            context['all_products'] = same_category_products

        if self.request.user.is_authenticated:
            try:
                            context['orderproduct'] = OrderProduct.objects.filter(
                                    user=self.request.user,
                                    product_id=self.object.id,
                                    order__is_ordered=True,
                                    order__payment__isnull=False,
                            ).exists()
            except OrderProduct.DoesNotExist:
               orderproduct = None
        else:
            orderproduct= None       
            
               
        return context
    
        
   
    
