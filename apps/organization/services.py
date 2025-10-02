from django.db import transaction
from django.utils import timezone
from decimal import Decimal
from .models import Profile, CreditsLedger, PackagePurchase


class CreditService:
    """Service class for managing credit operations."""
    
    @staticmethod
    @transaction.atomic
    def deduct_credits(organization, amount, description, related_appointment=None):
        """
        Deduct credits from an organization's balance.
        
        Args:
            organization: Profile instance
            amount: Decimal amount to deduct (positive value)
            description: String description of the deduction
            related_appointment: Optional Appointment instance
        
        Returns:
            CreditsLedger instance
        
        Raises:
            ValueError: If insufficient balance or invalid amount
        """
        if amount <= 0:
            raise ValueError("Deduction amount must be positive.")
        
        if organization.current_credits_balance < amount:
            raise ValueError(
                f"Insufficient credits. Balance: {organization.current_credits_balance}, "
                f"Required: {amount}"
            )
        
        balance_before = organization.current_credits_balance
        organization.current_credits_balance -= amount
        organization.version += 1
        organization.save(update_fields=['current_credits_balance', 'version', 'updated_at'])
        
        ledger_entry = CreditsLedger.objects.create(
            organization=organization,
            transaction_type='Deduction',
            amount=-amount,  # Negative for deductions
            balance_before=balance_before,
            balance_after=organization.current_credits_balance,
            description=description,
            related_appointment=related_appointment
        )
        
        return ledger_entry
    
    @staticmethod
    @transaction.atomic
    def add_credits(organization, amount, transaction_type, description, created_by=None):
        """
        Add credits to an organization's balance.
        
        Args:
            organization: Profile instance
            amount: Decimal amount to add
            transaction_type: String ('Purchase', 'Bonus', 'Refund', 'Adjustment')
            description: String description
            created_by: Optional User instance
        
        Returns:
            CreditsLedger instance
        """
        if amount <= 0:
            raise ValueError("Credit amount must be positive.")
        
        if transaction_type not in ['Purchase', 'Bonus', 'Refund', 'Adjustment']:
            raise ValueError(f"Invalid transaction type: {transaction_type}")
        
        balance_before = organization.current_credits_balance
        organization.current_credits_balance += amount
        organization.version += 1
        organization.save(update_fields=['current_credits_balance', 'version', 'updated_at'])
        
        ledger_entry = CreditsLedger.objects.create(
            organization=organization,
            transaction_type=transaction_type,
            amount=amount,
            balance_before=balance_before,
            balance_after=organization.current_credits_balance,
            description=description,
            created_by=created_by
        )
        
        return ledger_entry
    
    @staticmethod
    def check_sufficient_balance(organization, required_amount):
        """
        Check if organization has sufficient credits.
        
        Returns:
            Boolean
        """
        return organization.current_credits_balance >= required_amount
    
    @staticmethod
    def get_balance_with_lock(organization_id):
        """
        Get organization with row-level lock for concurrent updates.
        
        Returns:
            Profile instance
        """
        return Profile.objects.select_for_update().get(id=organization_id)