import json
from django.shortcuts import render, redirect
from django.views.generic import TemplateView
from django.views import View
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from payments import RedirectNeeded
from .models import Payment
import stripe
from django.conf import settings

# Set Stripe API key
stripe.api_key = settings.PAYMENT_VARIANTS['stripe'][1]['secret_key']


class StripeCheckoutView(TemplateView):
    template_name = 'stripe_checkout.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['stripe_public_key'] = settings.PAYMENT_VARIANTS['stripe'][1]['public_key']
        return context


@method_decorator(csrf_exempt, name='dispatch')
class CreateCheckoutSessionView(View):
    def post(self, request, *args, **kwargs):
        try:
            # Parse JSON data from request body
            data = json.loads(request.body)
            email = data.get('email', '')
            
            # Create Stripe Checkout Session
            checkout_session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': 'usd',
                        'product_data': {
                            'name': 'Fixed Payment',
                            'description': 'Your $20 payment',
                        },
                        'unit_amount': 2000,  # $20.00 in cents
                    },
                    'quantity': 1,
                }],
                mode='payment',
                success_url=request.build_absolute_uri('/payment/success/'),
                cancel_url=request.build_absolute_uri('/'),
                customer_email=email,  # Use email from JSON data
            )
            
            # Create django-payments Payment object
            payment = Payment.objects.create(
                variant='stripe',
                description='Fixed $20 Payment',
                total=20.00,
                currency='USD',
                billing_email=email,
                customer_ip_address=request.META.get('REMOTE_ADDR'),
                token=checkout_session.id,
            )
            
            return JsonResponse({
                'id': checkout_session.id,
                'url': checkout_session.url,
                'payment_id': payment.id
            })
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON data'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)


def success_view(request):
    return render(request, 'success.html')


def failure_view(request):
    return render(request, 'failure.html')