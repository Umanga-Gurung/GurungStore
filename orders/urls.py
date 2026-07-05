from django.urls import path
from .import views

urlpatterns = [
    path('place_order/',views.place_order,  name='place-order'),
    path('payments/', views.payments,name='payments'),
    path('order_complete/', views.order_complete,name='order_complete'),

    path('esewarequest/',views.EsewaRequestView.as_view(),name='esewarequest'),
    path('esewa-verify/',views.EsewaVerifyView.as_view(),name='esewaverify'),

    # Delivery Personnel Routes
    path('delivery/dashboard/', views.delivery_dashboard, name='delivery_dashboard'),
    path('delivery/order/<int:order_id>/', views.delivery_order_detail, name='delivery_order_detail'),
    path('delivery/start/<int:order_id>/', views.start_delivery, name='start_delivery'),
    path('delivery/send-otp/<int:order_id>/', views.send_delivery_otp, name='send_delivery_otp'),
    path('delivery/verify-otp/<int:order_id>/', views.verify_delivery_otp, name='verify_delivery_otp'),
    path('delivery/history/', views.delivery_history, name='delivery_history'),
    path('delivery/profile/', views.delivery_profile, name='delivery_profile'),
    path('delivery/login/', views.delivery_login, name='delivery_login'),
]
