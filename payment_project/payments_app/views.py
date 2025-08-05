import json
from django.shortcuts import render, redirect
from django.views.generic import TemplateView
from django.views import View
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.utils import timezone
from payments import RedirectNeeded
from .models import Payment
import stripe
from django.conf import settings
import logging

# Set up logging
logger = logging.getLogger(__name__)

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
                metadata={
                    'payment_id': 'fixed_20_payment',
                    'customer_email': email,
                }
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
                status='pending',  # Set initial status
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


@csrf_exempt
def stripe_webhook(request):
    """
    Handle Stripe webhook events
    """
    if request.method != 'POST':
        return HttpResponse(status=405)
    
    # Get the webhook secret from settings (you'll need to add this)
    webhook_secret = getattr(settings, 'STRIPE_WEBHOOK_SECRET', None)
    
    # Get the webhook data
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    
    try:
        # Verify webhook signature
        if webhook_secret:
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
        else:
            # For local testing without signature verification
            event = json.loads(payload)
            logger.warning("Webhook signature verification disabled - for local testing only")
        
        # Handle the event
        print(f"🎯 Processing webhook event: {event['type']}")
        
        if event['type'] == 'checkout.session.completed':
            session = event['data']['object']
            print(f"💰 Processing checkout.session.completed")
            handle_checkout_session_completed(session)
            
        elif event['type'] == 'checkout.session.expired':
            session = event['data']['object']
            print(f"⏰ Processing checkout.session.expired")
            handle_checkout_session_expired(session)
            
        elif event['type'] == 'payment_intent.payment_failed':
            payment_intent = event['data']['object']
            print(f"❌ Processing payment_intent.payment_failed")
            handle_payment_intent_failed(payment_intent)
            
        else:
            # Log unknown event types
            print(f"❓ Unhandled event type: {event['type']}")
        
        return HttpResponse(status=200)
        
    except ValueError as e:
        # Invalid payload
        logger.error(f"Invalid payload: {e}")
        return HttpResponse(status=400)
        
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        logger.error(f"Invalid signature: {e}")
        return HttpResponse(status=400)
        
    except Exception as e:
        # Unexpected error
        logger.error(f"Webhook error: {e}")
        return HttpResponse(status=500)


def handle_checkout_session_completed(session):
    """
    Handle successful payment completion
    """
    try:
        # Find the payment by session ID
        session_id = session['id']
        print(f"🔍 Processing checkout.session.completed for session: {session_id}")
        
        # List all payments for debugging
        all_payments = Payment.objects.all()
        print(f"📊 Total payments in database: {all_payments.count()}")
        for payment in all_payments:
            print(f"💳 Payment {payment.id}: token={payment.token}, status={payment.status}")
        
        payment = Payment.objects.get(token=session_id)
        
        # Update payment status
        payment.status = 'confirmed'
        payment.stripe_payment_intent_id = session.get('payment_intent')
        payment.payment_method = session.get('payment_method_types', ['card'])[0] if session.get('payment_method_types') else 'card'
        payment.webhook_received_at = timezone.now()
        payment.save()
        
        print(f"✅ Payment {payment.id} confirmed via webhook")
        
    except Payment.DoesNotExist:
        print(f"❌ Payment not found for session {session['id']}")
        print(f"🔍 Available session tokens: {list(Payment.objects.values_list('token', flat=True))}")
    except Exception as e:
        print(f"❌ Error processing checkout.session.completed: {e}")


def handle_checkout_session_expired(session):
    """
    Handle expired checkout session
    """
    try:
        payment = Payment.objects.get(token=session['id'])
        payment.status = 'expired'
        payment.webhook_received_at = timezone.now()
        payment.save()
        
        logger.info(f"Payment {payment.id} expired via webhook")
        
    except Payment.DoesNotExist:
        logger.error(f"Payment not found for session {session['id']}")
    except Exception as e:
        logger.error(f"Error processing checkout.session.expired: {e}")


def handle_payment_intent_failed(payment_intent):
    """
    Handle failed payment
    """
    try:
        # Find payment by payment intent ID
        payment = Payment.objects.get(stripe_payment_intent_id=payment_intent['id'])
        payment.status = 'failed'
        payment.webhook_received_at = timezone.now()
        payment.save()
        
        logger.info(f"Payment {payment.id} failed via webhook")
        
    except Payment.DoesNotExist:
        logger.error(f"Payment not found for payment intent {payment_intent['id']}")
    except Exception as e:
        logger.error(f"Error processing payment_intent.payment_failed: {e}")


def success_view(request):
    # Get the most recent payment for this session
    try:
        # Get the latest payment (most recent)
        payment = Payment.objects.latest('created_at')
        print(f"Success view - Payment {payment.id}: status={payment.status}")
        
        context = {
            'payment': payment,
            'payment_status': payment.status,
            'payment_confirmed': payment.status == 'confirmed',
            'payment_pending': payment.status == 'pending',
            'payment_failed': payment.status == 'failed',
        }
        
    except Payment.DoesNotExist:
        print("Success view - No payments found in database")
        context = {
            'payment': None,
            'payment_status': 'unknown',
            'payment_confirmed': False,
            'payment_pending': False,
            'payment_failed': False,
        }
    
    return render(request, 'success.html', context)


def failure_view(request):
    # Get the most recent payment for this session
    try:
        # Get the latest payment (most recent)
        payment = Payment.objects.latest('created_at')
        print(f"Failure view - Payment {payment.id}: status={payment.status}")
        
        context = {
            'payment': payment,
            'payment_status': payment.status,
            'payment_failed': payment.status == 'failed',
            'payment_expired': payment.status == 'expired',
            'payment_pending': payment.status == 'pending',
        }
        
    except Payment.DoesNotExist:
        print("Failure view - No payments found in database")
        context = {
            'payment': None,
            'payment_status': 'unknown',
            'payment_failed': False,
            'payment_expired': False,
            'payment_pending': False,
        }
    
    return render(request, 'failure.html', context)