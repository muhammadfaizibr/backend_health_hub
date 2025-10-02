from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ProfileViewSet, CreditPackageViewSet, CreditsLedgerViewSet, PackagePurchaseViewSet
)

router = DefaultRouter()
router.register(r'profiles', ProfileViewSet)
router.register(r'credit-packages', CreditPackageViewSet)
router.register(r'credits-ledger', CreditsLedgerViewSet)
router.register(r'package-purchases', PackagePurchaseViewSet)

urlpatterns = [
    path('', include(router.urls)),
]