"""
Staff pages for the Dashboard app: wallet withdrawals, affiliate payouts, Monnify payments,
transactions, accounts, tiers, boosts and referrals.

Rules used throughout:
  - Every view is staff-only. Moving money by hand (bonus credit) is superuser-only.
  - Lists never change data on GET. Every change is a POST.
  - Anything that touches a balance runs inside transaction.atomic() on a row locked with
    select_for_update(), and re-checks the status after the lock, so a double click or a
    second admin cannot apply the same action twice.
"""
import logging
from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db import transaction as db_transaction
from django.db.models import Count, Q, Sum
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .admin_forms import AffiliateSettingsForm, BonusForm, TierAdminForm
from .models import (AccountStatus, AffiliateCommission, AffiliateProfile, AffiliateWithdrawal,
                     MonnifyTransaction, ProductBoost, Referral, Transaction, UserAccount,
                     VirtualAccount, WalletTransfer, WithdrawalRequest)

logger = logging.getLogger(__name__)

PAGE_SIZE = 20
MAX_BATCH = 200  # most Monnify payments processed by one click

staff_required = user_passes_test(lambda u: u.is_active and u.is_staff)
superuser_required = user_passes_test(lambda u: u.is_active and u.is_superuser)


# --------------------------------------------------------------------------- helpers
def _next(request, fallback, *args):
    target = request.POST.get('next') or request.GET.get('next') or ''
    if target and url_has_allowed_host_and_scheme(
            target, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return target
    return reverse(fallback, args=args)


def _paginate(request, qs, size=PAGE_SIZE):
    paginator = Paginator(qs, size)
    try:
        return paginator.page(request.GET.get('page'))
    except PageNotAnInteger:
        return paginator.page(1)
    except EmptyPage:
        return paginator.page(paginator.num_pages)


def _keep(request):
    q = request.GET.copy()
    q.pop('page', None)
    return q.urlencode()


def _reason(request, limit=500):
    return (request.POST.get('reason') or '').strip()[:limit + 1]


def _tabs(spec, counts, current):
    """spec: [(key, label, tint)]. Returns the list the _ox_tabs partial expects."""
    tabs = [{'key': k, 'label': l, 'tint': t, 'count': counts.get(k, 0)} for k, l, t in spec]
    return tabs, (current if current in {k for k, _, _ in spec} else spec[0][0])


def _money(value):
    return f'₦{Decimal(value):,.2f}'


# =========================================================================== wallet withdrawals
WD_TABS = [('pending', 'Pending', 't-orange'), ('under_review', 'Under review', 't-navy'),
           ('approved', 'Approved', 't-navy'), ('processing', 'Processing', 't-navy'),
           ('completed', 'Completed', 't-green'), ('rejected', 'Rejected', 't-red'),
           ('cancelled', 'Cancelled', 't-navy'), ('all', 'All', 't-navy')]


@staff_required
def withdrawal_list(request):
    q = (request.GET.get('q') or '').strip()
    base = WithdrawalRequest.objects.all()
    agg = base.values('status').annotate(n=Count('id'))
    counts = {row['status']: row['n'] for row in agg}
    counts['all'] = sum(counts.values())
    tabs, status = _tabs(WD_TABS, counts, request.GET.get('status', 'pending'))

    qs = base.select_related('account__user')
    if status != 'all':
        qs = qs.filter(status=status)
    if q:
        qs = qs.filter(Q(reference__icontains=q) | Q(account__user__username__icontains=q)
                       | Q(account__user__email__icontains=q) | Q(account_number__icontains=q))
    qs = qs.order_by('submitted_at' if status in ('pending', 'under_review', 'approved', 'processing') else '-submitted_at')

    return render(request, 'admin/dash_withdrawals.html', {
        'page_obj': _paginate(request, qs), 'keep': _keep(request), 'tabs': tabs, 'status': status,
        'q': q, 'open_count': counts.get('pending', 0) + counts.get('under_review', 0),
        'to_pay': counts.get('approved', 0) + counts.get('processing', 0),
        'next_url': request.get_full_path(),
    })


@staff_required
def withdrawal_detail(request, pk):
    wr = get_object_or_404(
        WithdrawalRequest.objects.select_related('account__user', 'monnify_transaction', 'reviewed_by', 'wallet_transaction'),
        pk=pk)
    account = wr.account
    withdrawable_now = account.withdrawable_balance

    warnings = []
    if not wr.is_final:
        if account.balance < wr.requested_amount:
            warnings.append(f'Wallet balance ({_money(account.balance)}) is below the requested amount. Completing will fail.')
        if withdrawable_now < wr.requested_amount:
            warnings.append(f'Withdrawable balance is now {_money(withdrawable_now)}, less than the {_money(wr.requested_amount)} requested. The user has spent or withdrawn money since submitting.')
        if not (wr.monnify_transaction_id or wr.monnify_reference_manual or wr.proof_upload):
            warnings.append('There is no proof of deposit on this request.')
        if wr.monnify_transaction_id and wr.monnify_transaction.user_account_id != wr.account_id:
            warnings.append('The linked Monnify payment belongs to a different user.')

    proof_is_image = bool(wr.proof_upload) and wr.proof_upload.name.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp'))
    others = (WithdrawalRequest.objects.filter(account=account).exclude(pk=wr.pk)
              .order_by('-submitted_at')[:5])

    return render(request, 'admin/dash_withdrawal_detail.html', {
        'wr': wr, 'account': account, 'withdrawable_now': withdrawable_now, 'warnings': warnings,
        'proof_is_image': proof_is_image, 'others': others,
        'can_review': wr.status == 'pending', 'can_approve': wr.status in ('pending', 'under_review'),
        'can_process': wr.status == 'approved', 'can_complete': wr.status in ('approved', 'processing'),
        'can_reject': wr.status in ('pending', 'under_review', 'approved'),
        'next_url': request.get_full_path(),
    })


@staff_required
@require_POST
def withdrawal_action(request, pk, action):
    back = _next(request, 'dash_admin_withdrawal_detail', pk)
    reason = _reason(request)
    allowed = {
        'review': ('pending',),
        'approve': ('pending', 'under_review'),
        'processing': ('approved',),
        'complete': ('approved', 'processing'),
        'reject': ('pending', 'under_review', 'approved'),
    }
    if action not in allowed:
        raise Http404

    if action == 'reject' and not reason:
        messages.error(request, 'A reason is required. The user sees it.')
        return redirect(back)
    if action == 'complete':
        if not reason:
            messages.error(request, 'Enter the bank transfer reference before completing.')
            return redirect(back)
        if len(reason) > 100:
            messages.error(request, 'The payment reference is too long (100 characters at most).')
            return redirect(back)

    try:
        with db_transaction.atomic():
            wr = WithdrawalRequest.objects.select_for_update().get(pk=pk)
            if wr.status not in allowed[action]:
                messages.info(request, f'That request is already {wr.get_status_display().lower()}. Nothing was changed.')
                return redirect(back)
            if action == 'review':
                wr.status, wr.reviewed_by, wr.reviewed_at = 'under_review', request.user, timezone.now()
                wr.save(update_fields=['status', 'reviewed_by', 'reviewed_at'])
                messages.success(request, f'{wr.reference} is now under review.')
            elif action == 'approve':
                wr.approve(admin_user=request.user)
                messages.success(request, f'{wr.reference} approved. Pay it out, then mark it complete.')
            elif action == 'processing':
                wr.start_processing()
                messages.success(request, f'{wr.reference} marked as processing.')
            elif action == 'complete':
                wr.complete(payment_reference=reason)  # deducts the wallet and records the transaction
                messages.success(request, f'{wr.reference} completed. {_money(wr.requested_amount)} deducted from the wallet.')
            elif action == 'reject':
                wr.reject(admin_user=request.user, reason=reason)
                messages.success(request, f'{wr.reference} rejected. The wallet was not touched.')
            logger.info('Staff %s: wallet withdrawal %s -> %s', request.user.pk, wr.reference, action)
    except ValueError as exc:  # raised by complete() when the wallet cannot cover it
        messages.error(request, str(exc))
    except WithdrawalRequest.DoesNotExist:
        raise Http404
    return redirect(back)


@staff_required
@require_POST
def withdrawal_notes(request, pk):
    wr = get_object_or_404(WithdrawalRequest, pk=pk)
    wr.admin_notes = (request.POST.get('admin_notes') or '').strip()[:2000]
    wr.save(update_fields=['admin_notes'])
    messages.success(request, 'Notes saved.')
    return redirect(_next(request, 'dash_admin_withdrawal_detail', pk))


# =========================================================================== affiliate payouts
PAYOUT_TABS = [('pending', 'Pending', 't-orange'), ('approved', 'Approved', 't-navy'),
               ('processing', 'Processing', 't-navy'), ('completed', 'Completed', 't-green'),
               ('rejected', 'Rejected', 't-red'), ('all', 'All', 't-navy')]


@staff_required
def payout_list(request):
    q = (request.GET.get('q') or '').strip()
    base = AffiliateWithdrawal.objects.all()
    counts = {r['status']: r['n'] for r in base.values('status').annotate(n=Count('id'))}
    counts['all'] = sum(counts.values())
    tabs, status = _tabs(PAYOUT_TABS, counts, request.GET.get('status', 'pending'))

    qs = base.select_related('affiliate__user', 'processed_by')
    if status != 'all':
        qs = qs.filter(status=status)
    if q:
        qs = qs.filter(Q(affiliate__referral_code__icontains=q) | Q(affiliate__user__username__icontains=q)
                       | Q(account_number__icontains=q) | Q(account_name__icontains=q))
    qs = qs.order_by('requested_at' if status in ('pending', 'approved', 'processing') else '-requested_at')

    open_total = base.filter(status__in=['pending', 'approved', 'processing']).aggregate(t=Sum('amount'))['t'] or 0
    return render(request, 'admin/dash_payouts.html', {
        'page_obj': _paginate(request, qs), 'keep': _keep(request), 'tabs': tabs, 'status': status,
        'q': q, 'open_total': open_total, 'next_url': request.get_full_path(),
    })


@staff_required
@require_POST
def payout_action(request, pk, action):
    """
    The affiliate's available balance is deducted when they request the payout (see
    affiliate_withdraw), so: reject gives it back, complete adds it to total_withdrawn.
    """
    back = _next(request, 'dash_admin_payouts')
    reason = _reason(request)
    allowed = {
        'approve': ('pending',),
        'processing': ('approved',),
        'complete': ('pending', 'approved', 'processing'),
        'reject': ('pending', 'approved'),
    }
    if action not in allowed:
        raise Http404
    if action == 'reject' and not reason:
        messages.error(request, 'A reason is required. The affiliate sees it.')
        return redirect(back)
    if action == 'complete':
        if not reason:
            messages.error(request, 'Enter the bank transfer reference before completing.')
            return redirect(back)
        if len(reason) > 100:
            messages.error(request, 'The payment reference is too long (100 characters at most).')
            return redirect(back)

    with db_transaction.atomic():
        wd = AffiliateWithdrawal.objects.select_for_update().select_related('affiliate').get(pk=pk)
        if wd.status not in allowed[action]:
            messages.info(request, f'That payout is already {wd.get_status_display().lower()}. Nothing was changed.')
            return redirect(back)
        affiliate = AffiliateProfile.objects.select_for_update().get(pk=wd.affiliate_id)
        now = timezone.now()
        if action == 'approve':
            wd.status = 'approved'
            wd.processed_by, wd.processed_at = request.user, now
            wd.save(update_fields=['status', 'processed_by', 'processed_at'])
            messages.success(request, f'{_money(wd.amount)} for {affiliate.referral_code} approved.')
        elif action == 'processing':
            wd.status = 'processing'
            wd.save(update_fields=['status'])
            messages.success(request, 'Marked as processing.')
        elif action == 'complete':
            wd.status, wd.payment_reference = 'completed', reason
            wd.processed_by, wd.processed_at = request.user, now
            wd.save(update_fields=['status', 'payment_reference', 'processed_by', 'processed_at'])
            affiliate.total_withdrawn += wd.amount
            affiliate.save(update_fields=['total_withdrawn'])
            messages.success(request, f'Payout of {_money(wd.amount)} to {affiliate.referral_code} completed.')
        elif action == 'reject':
            wd.status, wd.rejection_reason = 'rejected', reason
            wd.processed_by, wd.processed_at = request.user, now
            wd.save(update_fields=['status', 'rejection_reason', 'processed_by', 'processed_at'])
            affiliate.available_balance += wd.amount
            affiliate.save(update_fields=['available_balance'])
            messages.success(request, f'Rejected. {_money(wd.amount)} returned to {affiliate.referral_code}\'s available balance.')
        logger.info('Staff %s: affiliate payout %s -> %s', request.user.pk, wd.pk, action)
    return redirect(back)


@staff_required
def affiliate_settings(request, affiliate_id):
    affiliate = get_object_or_404(AffiliateProfile.objects.select_related('user'), pk=affiliate_id)
    if request.method == 'POST':
        form = AffiliateSettingsForm(request.POST, instance=affiliate)
        if form.is_valid():
            form.save()
            messages.success(request, 'Affiliate settings saved. New rates apply to future commissions only.')
            return redirect('admin_affiliate_detail', affiliate_id=affiliate.pk)
        messages.error(request, 'Fix the highlighted fields and save again.')
    else:
        form = AffiliateSettingsForm(instance=affiliate)
    return render(request, 'admin/dash_affiliate_settings.html', {'form': form, 'affiliate': affiliate})


# =========================================================================== payments (Monnify)
PAY_TABS = [('unprocessed', 'Not credited', 't-orange'), ('processed', 'Credited', 't-green'),
            ('other', 'Not paid', 't-red'), ('all', 'All', 't-navy')]


@staff_required
def payment_list(request):
    tab = request.GET.get('tab', 'deposits')
    q = (request.GET.get('q') or '').strip()

    if tab == 'accounts':
        qs = VirtualAccount.objects.select_related('user_account__user')
        status = request.GET.get('status', 'all')
        counts = {r['status']: r['n'] for r in VirtualAccount.objects.values('status').annotate(n=Count('id'))}
        counts['all'] = sum(counts.values())
        tabs, status = _tabs([('active', 'Active', 't-green'), ('inactive', 'Inactive', 't-navy'),
                              ('suspended', 'Suspended', 't-red'), ('all', 'All', 't-navy')], counts, status)
        if status != 'all':
            qs = qs.filter(status=status)
        if q:
            qs = qs.filter(Q(account_number__icontains=q) | Q(account_name__icontains=q)
                           | Q(user_account__user__username__icontains=q))
        return render(request, 'admin/dash_payments.html', {
            'tab': 'accounts', 'page_obj': _paginate(request, qs.order_by('-created_at')), 'keep': _keep(request),
            'tabs': tabs, 'status': status, 'q': q, 'next_url': request.get_full_path(),
            'head_value': counts['all'], 'head_label': 'Virtual accounts',
        })

    base = MonnifyTransaction.objects.all()
    # Aliases must not share a name with a model field (`processed`), or later filters resolve to the alias.
    raw = base.aggregate(
        n_all=Count('id'),
        n_unprocessed=Count('id', filter=Q(payment_status='PAID', processed=False)),
        n_credited=Count('id', filter=Q(processed=True)),
        n_other=Count('id', filter=~Q(payment_status='PAID') & Q(processed=False)),
    )
    agg = {'all': raw['n_all'], 'unprocessed': raw['n_unprocessed'],
           'processed': raw['n_credited'], 'other': raw['n_other']}
    tabs, status = _tabs(PAY_TABS, agg, request.GET.get('status', 'unprocessed'))
    qs = base.select_related('user_account__user')
    if status == 'unprocessed':
        qs = qs.filter(payment_status='PAID', processed=False)
    elif status == 'processed':
        qs = qs.filter(processed=True)
    elif status == 'other':
        qs = qs.filter(processed=False).exclude(payment_status='PAID')
    if q:
        qs = qs.filter(Q(transaction_reference__icontains=q) | Q(payment_reference__icontains=q)
                       | Q(user_account__user__username__icontains=q) | Q(customer_email__icontains=q))
    return render(request, 'admin/dash_payments.html', {
        'tab': 'deposits', 'page_obj': _paginate(request, qs.order_by('-paid_on')), 'keep': _keep(request),
        'tabs': tabs, 'status': status, 'q': q, 'next_url': request.get_full_path(),
        'head_value': agg['unprocessed'], 'head_label': 'Paid, not credited', 'pending_count': agg['unprocessed'],
    })


def _process_locked(pk):
    """Credit one payment. Locks the row and re-checks, so the webhook and a click cannot both credit it."""
    with db_transaction.atomic():
        mt = MonnifyTransaction.objects.select_for_update().select_related('user_account__user').get(pk=pk)
        if mt.processed or mt.payment_status != 'PAID':
            return None
        # process_payment() swallows its own errors and returns False, so an
        # exception inside add_funds cannot leave a half-credited row behind.
        return mt, mt.process_payment()


@staff_required
@require_POST
def payment_process(request, pk):
    result = _process_locked(pk)
    if result is None:
        messages.info(request, 'That payment is already credited or is not marked as paid.')
    else:
        mt, ok = result
        if ok:
            messages.success(request, f'{_money(mt.amount_paid)} credited to {mt.user_account.user.username}.')
            logger.info('Staff %s credited Monnify payment %s', request.user.pk, mt.transaction_reference)
        else:
            messages.error(request, 'Crediting failed. The error is in the server log.')
    return redirect(_next(request, 'dash_admin_payments'))


@staff_required
@require_POST
def payment_process_all(request):
    ids = list(MonnifyTransaction.objects.filter(payment_status='PAID', processed=False)
               .order_by('paid_on').values_list('pk', flat=True)[:MAX_BATCH])
    done = failed = 0
    for pk in ids:
        result = _process_locked(pk)
        if result is None:
            continue
        done, failed = (done + 1, failed) if result[1] else (done, failed + 1)
    msg = f'Credited {done} payment(s).'
    if failed:
        msg += f' {failed} failed, see the server log.'
    if len(ids) == MAX_BATCH:
        msg += f' Stopped at {MAX_BATCH}. Run it again for the rest.'
    (messages.error if failed else messages.success)(request, msg)
    logger.info('Staff %s batch-credited Monnify payments: %s ok, %s failed', request.user.pk, done, failed)
    return redirect(_next(request, 'dash_admin_payments'))


# =========================================================================== transactions + transfers
TXN_TYPES = [t for t in UserAccount.TRANSACTION_TYPES]


@staff_required
def transaction_list(request):
    tab = request.GET.get('tab', 'transactions')
    q = (request.GET.get('q') or '').strip()

    if tab == 'transfers':
        status = request.GET.get('status', 'all')
        qs = WalletTransfer.objects.select_related('sender__user', 'recipient__user')
        if status in ('completed', 'failed', 'reversed'):
            qs = qs.filter(status=status)
        else:
            status = 'all'
        if q:
            qs = qs.filter(Q(reference__icontains=q) | Q(sender__user__username__icontains=q)
                           | Q(recipient__user__username__icontains=q))
        total = qs.filter(status='completed').aggregate(t=Sum('amount'))['t'] or 0
        return render(request, 'admin/dash_transactions.html', {
            'tab': 'transfers', 'page_obj': _paginate(request, qs.order_by('-created_at')), 'keep': _keep(request),
            'status': status, 'q': q, 'total': total, 'next_url': request.get_full_path(),
            'statuses': [('all', 'All'), ('completed', 'Completed'), ('failed', 'Failed'), ('reversed', 'Reversed')],
        })

    ttype = request.GET.get('type', '')
    direction = request.GET.get('dir', '')
    qs = Transaction.objects.select_related('account__user')
    if ttype in dict(TXN_TYPES):
        qs = qs.filter(transaction_type=ttype)
    else:
        ttype = ''
    if direction == 'in':
        qs = qs.filter(amount__gt=0)
    elif direction == 'out':
        qs = qs.filter(amount__lt=0)
    else:
        direction = ''
    if q:
        qs = qs.filter(Q(account__user__username__icontains=q) | Q(account__user__email__icontains=q)
                       | Q(description__icontains=q) | Q(reference_id__icontains=q))
    sums = qs.aggregate(count=Count('id'), money_in=Sum('amount', filter=Q(amount__gt=0)),
                        money_out=Sum('amount', filter=Q(amount__lt=0)))
    return render(request, 'admin/dash_transactions.html', {
        'tab': 'transactions', 'page_obj': _paginate(request, qs.order_by('-created_at')), 'keep': _keep(request),
        'type': ttype, 'dir': direction, 'q': q, 'types': TXN_TYPES, 'sums': sums,
        'money_in': sums['money_in'] or 0, 'money_out': abs(sums['money_out'] or 0),
        'next_url': request.get_full_path(),
    })


# =========================================================================== accounts
@staff_required
def account_list(request):
    q = (request.GET.get('q') or '').strip()
    tier = request.GET.get('tier', 'all')
    base = UserAccount.objects.select_related('user', 'status')
    counts = base.aggregate(
        all=Count('id'),
        paid=Count('id', filter=Q(status__tier_type__in=['pro', 'enterprise'])),
        free=Count('id', filter=~Q(status__tier_type__in=['pro', 'enterprise'])),
    )
    wallet_total = UserAccount.objects.aggregate(t=Sum('balance'))['t'] or 0
    qs = base
    if tier == 'paid':
        qs = qs.filter(status__tier_type__in=['pro', 'enterprise'])
    elif tier == 'free':
        qs = qs.exclude(status__tier_type__in=['pro', 'enterprise'])
    else:
        tier = 'all'
    if q:
        qs = qs.filter(Q(user__username__icontains=q) | Q(user__email__icontains=q))
    qs = qs.order_by('-balance', 'user__username')
    tabs, tier = _tabs([('paid', 'Pro tier', 't-green'), ('free', 'Free tier', 't-navy'), ('all', 'All', 't-navy')],
                       counts, tier)
    page = _paginate(request, qs)
    for acc in page.object_list:
        info = acc.subscription_info
        acc.sub = info if info and info['active'] else None
        acc.sub_expired = bool(info and not info['active'])
        acc.sub_days = (info['end_date'] - timezone.now()).days if acc.sub else None
    return render(request, 'admin/dash_accounts.html', {
        'page_obj': page, 'keep': _keep(request), 'tabs': tabs, 'tier': tier, 'q': q,
        'wallet_total': wallet_total, 'next_url': request.get_full_path(), 'cols': 3,
    })


@staff_required
def account_detail(request, pk):
    account = get_object_or_404(UserAccount.objects.select_related('user', 'status'), pk=pk)
    sub = account.subscription_info
    txns = account.transactions.order_by('-created_at')[:15]
    return render(request, 'admin/dash_account_detail.html', {
        'account': account, 'sub': sub, 'sub_active': bool(sub and sub['active']),
        'effective': account.effective_status,
        'deposited': account.deposited_balance, 'withdrawn': account.total_withdrawn,
        'withdrawable': account.withdrawable_balance, 'bonus': account.bonus_balance,
        'txns': txns, 'wds': account.withdrawal_requests.order_by('-submitted_at')[:5],
        'boosts': account.product_boosts.select_related('product').order_by('-start_date')[:5],
        'vaccounts': account.virtual_accounts.all(),
        'bonus_form': BonusForm(), 'can_credit': request.user.is_superuser,
        'affiliate': AffiliateProfile.objects.filter(user_id=account.user_id).first(),
        'next_url': request.get_full_path(),
    })


@staff_required
@require_POST
def account_recheck(request, pk):
    account = get_object_or_404(UserAccount, pk=pk)
    before = account.status_id
    account.check_and_update_status()
    messages.success(request, 'Tier updated to match the subscription.' if account.status_id != before
                     else 'Checked. The tier was already correct.')
    return redirect(_next(request, 'dash_admin_account', pk))


@superuser_required
@require_POST
def account_credit(request, pk):
    back = reverse('dash_admin_account', args=[pk])
    form = BonusForm(request.POST)
    if not form.is_valid():
        for errs in form.errors.values():
            messages.error(request, errs[0])
        return redirect(back)
    amount, reason = form.cleaned_data['amount'], form.cleaned_data['reason']
    with db_transaction.atomic():
        account = UserAccount.objects.select_for_update().select_related('user').get(pk=pk)
        # 'bonus' credits are not withdrawable and earn no affiliate commission.
        account.add_funds(amount, transaction_type='bonus',
                          description=f'Admin credit: {reason}'[:255])
    logger.info('Superuser %s credited %s to account %s: %s', request.user.pk, amount, pk, reason)
    messages.success(request, f'{_money(amount)} credited to {account.user.username}.')
    return redirect(back)


# =========================================================================== tiers
@staff_required
def tier_list(request):
    tiers = AccountStatus.objects.annotate(n_accounts=Count('accounts')).order_by('tier_type', 'monthly_price')
    return render(request, 'admin/dash_tiers.html', {'tiers': tiers})


@staff_required
def tier_form(request, pk=None):
    tier = get_object_or_404(AccountStatus, pk=pk) if pk else None
    if request.method == 'POST':
        form = TierAdminForm(request.POST, instance=tier)
        if form.is_valid():
            form.save()
            messages.success(request, 'Tier saved.' if tier else 'Tier added.')
            return redirect('dash_admin_tiers')
        messages.error(request, 'Fix the highlighted fields and save again.')
    else:
        form = TierAdminForm(instance=tier)
    return render(request, 'admin/dash_tier_form.html', {
        'form': form, 'tier': tier,
        'n_accounts': tier.accounts.count() if tier else 0,
    })


# =========================================================================== boosts
BOOST_TABS = [('active', 'Running', 't-green'), ('expiring', 'Ending in 24h', 't-orange'),
              ('expired', 'Expired', 't-red'), ('inactive', 'Switched off', 't-navy'), ('all', 'All', 't-navy')]


@staff_required
def boost_list(request):
    now = timezone.now()
    soon = now + timedelta(hours=24)
    q = (request.GET.get('q') or '').strip()
    base = ProductBoost.objects.all()
    counts = base.aggregate(
        active=Count('id', filter=Q(is_active=True, end_date__gt=now)),
        expiring=Count('id', filter=Q(is_active=True, end_date__gt=now, end_date__lte=soon)),
        expired=Count('id', filter=Q(end_date__lte=now)),
        inactive=Count('id', filter=Q(is_active=False)),
        all=Count('id'),
    )
    tabs, status = _tabs(BOOST_TABS, counts, request.GET.get('status', 'active'))
    qs = base.select_related('product', 'user_account__user')
    if status == 'active':
        qs = qs.filter(is_active=True, end_date__gt=now)
    elif status == 'expiring':
        qs = qs.filter(is_active=True, end_date__gt=now, end_date__lte=soon).order_by('end_date')
    elif status == 'expired':
        qs = qs.filter(end_date__lte=now)
    elif status == 'inactive':
        qs = qs.filter(is_active=False)
    if q:
        qs = qs.filter(Q(product__title__icontains=q) | Q(user_account__user__username__icontains=q))
    revenue = base.aggregate(
        total=Sum('final_cost'), month=Sum('final_cost', filter=Q(start_date__gte=now - timedelta(days=30))))
    page = _paginate(request, qs.order_by('end_date') if status == 'expiring' else qs)
    for b in page.object_list:
        if not b.is_active:
            b.state, b.state_label = 'inactive', 'Switched off'
        elif b.is_expired:
            b.state, b.state_label = 'expired', 'Expired'
        elif b.end_date <= soon:
            b.state, b.state_label = 'expiring', 'Ends soon'
        else:
            b.state, b.state_label = 'active', 'Running'
        b.can_cancel = b.is_active and not b.is_expired
        b.can_activate = (not b.is_active) and not b.is_expired
    return render(request, 'admin/dash_boosts.html', {
        'page_obj': page, 'keep': _keep(request), 'tabs': tabs, 'status': status, 'q': q,
        'revenue': revenue, 'running': counts['active'], 'next_url': request.get_full_path(),
    })


@staff_required
@require_POST
def boost_action(request, pk, action):
    back = _next(request, 'dash_admin_boosts')
    if action not in ('deactivate', 'activate', 'cancel'):
        raise Http404
    with db_transaction.atomic():
        boost = (ProductBoost.objects.select_for_update().select_related('product', 'user_account__user').get(pk=pk))
        title = boost.product.title
        if action == 'deactivate':
            if not boost.is_active:
                messages.info(request, 'That boost is already switched off.')
            else:
                boost.is_active = False
                boost.save(update_fields=['is_active'])
                messages.success(request, f'Boost on "{title}" switched off. No refund was given.')
        elif action == 'activate':
            if boost.is_expired:
                messages.error(request, 'That boost has expired and cannot be switched back on.')
            elif boost.is_active:
                messages.info(request, 'That boost is already running.')
            else:
                boost.is_active = True
                boost.save(update_fields=['is_active'])
                messages.success(request, f'Boost on "{title}" switched on.')
        else:  # cancel with a full refund of the unused whole days
            # ProductBoost.cancel_boost() multiplies a Decimal by a float and raises TypeError,
            # so the refund is worked out here instead.
            if not boost.is_active or boost.is_expired:
                messages.error(request, 'Only a running boost can be cancelled.')
            else:
                days_left = boost.days_remaining  # whole days
                refund = (boost.final_cost / boost.duration_days * days_left).quantize(Decimal('0.01'))
                account = UserAccount.objects.select_for_update().get(pk=boost.user_account_id)
                if refund > 0:
                    account.add_funds(refund, transaction_type='refund',
                                      description=f'Refund for cancelled {boost.boost_type} boost ({days_left} days left)'[:255])
                boost.is_active = False
                boost.end_date = timezone.now()
                boost.save(update_fields=['is_active', 'end_date'])
                if refund > 0:
                    messages.success(request, f'Boost on "{title}" cancelled. {_money(refund)} refunded to {boost.user_account.user.username}.')
                else:
                    messages.success(request, f'Boost on "{title}" cancelled. Less than a full day was left, so no refund was due.')
                logger.info('Staff %s cancelled boost %s, refund %s', request.user.pk, pk, refund)
    return redirect(back)


# =========================================================================== referrals + commissions
REF_TABS = [('flagged', 'Flagged', 't-orange'), ('fraud', 'Fraud', 't-red'), ('active', 'Active', 't-green'),
            ('pending', 'Pending', 't-navy'), ('inactive', 'Inactive', 't-navy'), ('all', 'All', 't-navy')]
COMM_TABS = [('pending', 'Pending', 't-orange'), ('available', 'Available', 't-green'),
             ('paid', 'Paid', 't-navy'), ('cancelled', 'Cancelled', 't-red'), ('all', 'All', 't-navy')]


@staff_required
def referral_list(request):
    tab = request.GET.get('tab', 'referrals')
    q = (request.GET.get('q') or '').strip()

    if tab == 'commissions':
        base = AffiliateCommission.objects.all()
        counts = {r['status']: r['n'] for r in base.values('status').annotate(n=Count('id'))}
        counts['all'] = sum(counts.values())
        tabs, status = _tabs(COMM_TABS, counts, request.GET.get('status', 'pending'))
        qs = base.select_related('affiliate__user', 'referral__referred_user')
        if status != 'all':
            qs = qs.filter(status=status)
        if q:
            qs = qs.filter(Q(affiliate__referral_code__icontains=q)
                           | Q(referral__referred_user__username__icontains=q))
        sums = qs.aggregate(total=Sum('commission_amount'))
        return render(request, 'admin/dash_referrals.html', {
            'tab': 'commissions', 'page_obj': _paginate(request, qs.order_by('-created_at')), 'keep': _keep(request),
            'tabs': tabs, 'status': status, 'q': q, 'total': sums['total'] or 0,
            'next_url': request.get_full_path(), 'cols': 5,
        })

    base = Referral.objects.all()
    counts = {r['status']: r['n'] for r in base.values('status').annotate(n=Count('id'))}
    counts['all'] = sum(counts.values())
    counts['flagged'] = base.filter(flagged_for_review=True).count()
    tabs, status = _tabs(REF_TABS, counts, request.GET.get('status', 'flagged'))
    qs = base.select_related('affiliate__user', 'referred_user')
    if status == 'flagged':
        qs = qs.filter(flagged_for_review=True)
    elif status != 'all':
        qs = qs.filter(status=status)
    if q:
        qs = qs.filter(Q(referred_user__username__icontains=q) | Q(affiliate__referral_code__icontains=q)
                       | Q(signup_ip__icontains=q))
    return render(request, 'admin/dash_referrals.html', {
        'tab': 'referrals', 'page_obj': _paginate(request, qs.order_by('-signup_date')), 'keep': _keep(request),
        'tabs': tabs, 'status': status, 'q': q, 'flagged': counts['flagged'],
        'next_url': request.get_full_path(), 'cols': 6,
    })


@staff_required
@require_POST
def referral_action(request, pk, action):
    back = _next(request, 'dash_admin_referrals')
    if action not in ('fraud', 'clear'):
        raise Http404
    reason = _reason(request, 1000)
    if action == 'fraud' and not reason:
        messages.error(request, 'A reason is required.')
        return redirect(back)

    with db_transaction.atomic():
        ref = Referral.objects.select_for_update().select_related('affiliate', 'referred_user').get(pk=pk)
        if action == 'clear':
            ref.flagged_for_review = False
            ref.fraud_reason = ''
            ref.status = 'active' if ref.first_qualifying_transaction else 'pending'
            ref.save(update_fields=['flagged_for_review', 'fraud_reason', 'status'])
            messages.success(request, f'{ref.referred_user.username} cleared and set back to {ref.status}.')
            return redirect(back)

        if ref.status == 'fraud':
            messages.info(request, 'Already marked as fraud.')
            return redirect(back)
        ref.status, ref.flagged_for_review, ref.fraud_reason = 'fraud', True, reason
        # Cancel commissions still on hold, the same way a refund reversal does.
        affiliate = AffiliateProfile.objects.select_for_update().get(pk=ref.affiliate_id)
        held = list(AffiliateCommission.objects.select_for_update().filter(referral=ref, status='pending'))
        total = sum((c.commission_amount for c in held), Decimal('0'))
        for c in held:
            c.status = 'cancelled'
            c.save(update_fields=['status'])
        if total:
            affiliate.pending_balance -= total
            affiliate.total_earned -= total
            affiliate.save(update_fields=['pending_balance', 'total_earned'])
            ref.total_commission_earned -= total
        ref.save(update_fields=['status', 'flagged_for_review', 'fraud_reason', 'total_commission_earned'])
        available = AffiliateCommission.objects.filter(referral=ref, status__in=['available', 'paid']).count()
        msg = f'{ref.referred_user.username} marked as fraud. {len(held)} held commission(s) cancelled ({_money(total)}).'
        if available:
            msg += f' {available} commission(s) were already released and were left alone.'
        messages.warning(request, msg)
        logger.info('Staff %s marked referral %s as fraud: %s', request.user.pk, pk, reason)
    return redirect(back)
