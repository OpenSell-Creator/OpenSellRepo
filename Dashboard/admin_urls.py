"""
Include from the project urls.py, above the 'controlroom/' admin route:
    path('controlroom/money/', include('Dashboard.admin_urls')),
Names are all prefixed dash_admin_ so they cannot clash with existing routes.
"""
from django.urls import path

from . import admin_views as v

urlpatterns = [
    path('withdrawals/', v.withdrawal_list, name='dash_admin_withdrawals'),
    path('withdrawals/<int:pk>/', v.withdrawal_detail, name='dash_admin_withdrawal_detail'),
    path('withdrawals/<int:pk>/notes/', v.withdrawal_notes, name='dash_admin_withdrawal_notes'),
    path('withdrawals/<int:pk>/<slug:action>/', v.withdrawal_action, name='dash_admin_withdrawal_action'),

    path('payouts/', v.payout_list, name='dash_admin_payouts'),
    path('payouts/<int:pk>/<slug:action>/', v.payout_action, name='dash_admin_payout_action'),
    path('affiliates/<int:affiliate_id>/settings/', v.affiliate_settings, name='dash_admin_affiliate_settings'),

    path('payments/', v.payment_list, name='dash_admin_payments'),
    path('payments/process-all/', v.payment_process_all, name='dash_admin_payment_process_all'),
    path('payments/<int:pk>/process/', v.payment_process, name='dash_admin_payment_process'),

    path('transactions/', v.transaction_list, name='dash_admin_transactions'),

    path('accounts/', v.account_list, name='dash_admin_accounts'),
    path('accounts/<int:pk>/', v.account_detail, name='dash_admin_account'),
    path('accounts/<int:pk>/recheck/', v.account_recheck, name='dash_admin_account_recheck'),
    path('accounts/<int:pk>/credit/', v.account_credit, name='dash_admin_account_credit'),

    path('tiers/', v.tier_list, name='dash_admin_tiers'),
    path('tiers/new/', v.tier_form, name='dash_admin_tier_new'),
    path('tiers/<int:pk>/edit/', v.tier_form, name='dash_admin_tier_edit'),

    path('boosts/', v.boost_list, name='dash_admin_boosts'),
    path('boosts/<int:pk>/<slug:action>/', v.boost_action, name='dash_admin_boost_action'),

    path('referrals/', v.referral_list, name='dash_admin_referrals'),
    path('referrals/<int:pk>/<slug:action>/', v.referral_action, name='dash_admin_referral_action'),
]
