from django.db import models
from payments.models import BasePayment
from django.urls import reverse

class Payment(BasePayment):
    # Override the token field to support longer Stripe IDs
    token = models.CharField(max_length=100, blank=True, db_index=True)

    def get_success_url(self):
        return reverse('payment_success')
    
    def get_failure_url(self):
        return reverse('payment_failure')