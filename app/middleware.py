from django.shortcuts import redirect
from django.urls import reverse

class DeliveryPersonRestrictionMiddleware:
    """
    Middleware that restricts Delivery Personnel to delivery-related pages only.
    If a delivery person tries to access customer/shopping routes, they are
    automatically redirected to their Delivery Dashboard.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and getattr(request.user, 'is_delivery_person', False):
            # Admins and superadmins are exempt from restrictions
            if not getattr(request.user, 'is_admin', False) and not getattr(request.user, 'is_superadmin', False):
                path = request.path
                allowed_prefixes = [
                    '/orders/delivery/',
                    '/accounts/logout/',
                    '/static/',
                    '/media/',
                ]
                is_allowed = any(path.startswith(prefix) for prefix in allowed_prefixes)
                if not is_allowed:
                    return redirect('delivery_dashboard')

        response = self.get_response(request)
        return response
