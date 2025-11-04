from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    PaymentMethodViewSet, TransactionViewSet, RefundViewSet,
    AppointmentBillingViewSet, WalletLedgerViewSet, PayoutRequestViewSet
)
from .views import PackagePurchaseView

app_name = 'billing'

router = DefaultRouter()
router.register(r'payment-methods', PaymentMethodViewSet, basename='payment-method')
router.register(r'transactions', TransactionViewSet, basename='transaction')
router.register(r'refunds', RefundViewSet, basename='refund')
router.register(r'billings', AppointmentBillingViewSet, basename='billing')
router.register(r'wallet-ledger', WalletLedgerViewSet, basename='wallet-ledger')
router.register(r'payout-requests', PayoutRequestViewSet, basename='payout-request')

urlpatterns = [
    path('', include(router.urls)),
    path('purchase-package/', PackagePurchaseView.as_view(), name='purchase-package'),
    path('purchase-package/<uuid:purchase_id>/confirm/', PackagePurchaseView.as_view(), name='confirm-purchase'),
]