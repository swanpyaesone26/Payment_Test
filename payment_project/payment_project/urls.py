"""
URL configuration for payment_project project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path,include  # ----added
from payments_app.views import StripeCheckoutView, CreateCheckoutSessionView, success_view, failure_view, stripe_webhook  # ----added


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', StripeCheckoutView.as_view(), name='stripe_checkout'),  # Stripe Checkout page
    path('create-checkout-session/', CreateCheckoutSessionView.as_view(), name='create_checkout_session'),
    path('payment/success/', success_view, name='payment_success'),
    path('payment/failure/', failure_view, name='payment_failure'), # ----added
    path('webhook/', stripe_webhook, name='stripe_webhook'),  # Stripe webhook endpoint
    path('payment/', include('payments.urls')),  # Include django-payments URLs
]
