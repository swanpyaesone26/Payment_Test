from django.db import models
from payments.models import BasePayment
from django.urls import reverse
from django.utils import timezone

class Payment(BasePayment):
    # Override the token field to support longer Stripe IDs
    token = models.CharField(max_length=100, blank=True, db_index=True)
    
    # Payment status tracking
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('failed', 'Failed'),
        ('expired', 'Expired'),
    ]
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='pending',
        db_index=True
    )
    
    # Stripe-specific tracking
    stripe_payment_intent_id = models.CharField(max_length=100, blank=True, null=True)
    payment_method = models.CharField(max_length=50, blank=True, null=True)
    webhook_received_at = models.DateTimeField(blank=True, null=True)
    
    # Timestamps for tracking
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def get_success_url(self):
        return reverse('payment_success')
    
    def get_failure_url(self):
        return reverse('payment_failure')
    
    def __str__(self):
        return f"Payment {self.id} - {self.status} - ${self.total}"
    
    class Meta:
        ordering = ['-created_at']