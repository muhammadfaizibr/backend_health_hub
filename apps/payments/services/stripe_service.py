import stripe
from django.conf import settings
from decimal import Decimal

stripe.api_key = settings.STRIPE_SECRET_KEY

class StripeService:
    @staticmethod
    def create_payment_intent(amount, currency='pkr', metadata=None):
        """Create a Stripe payment intent."""
        try:
            # Stripe requires amount in smallest currency unit (paisa for PKR)
            amount_in_paisa = int(amount * 100)
            
            intent = stripe.PaymentIntent.create(
                amount=amount_in_paisa,
                currency=currency.lower(),
                metadata=metadata or {},
                payment_method_types=['card'],
            )
            return intent
        except stripe.error.StripeError as e:
            raise Exception(f"Stripe error: {str(e)}")
    
    @staticmethod
    def confirm_payment(payment_intent_id):
        """Confirm a payment intent."""
        try:
            intent = stripe.PaymentIntent.retrieve(payment_intent_id)
            return intent
        except stripe.error.StripeError as e:
            raise Exception(f"Stripe error: {str(e)}")
    
    @staticmethod
    def create_refund(payment_intent_id, amount=None):
        """Create a refund."""
        try:
            refund = stripe.Refund.create(
                payment_intent=payment_intent_id,
                amount=int(amount * 100) if amount else None,
            )
            return refund
        except stripe.error.StripeError as e:
            raise Exception(f"Stripe error: {str(e)}")