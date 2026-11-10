"""
Staff pages for the Notifications app: send a broadcast, see and withdraw what was sent,
browse every notification, and run clean-up and push checks.

Every view is staff-only, every change is a POST, and sending to "Everyone" is superuser-only.
"""
import logging
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.models import User
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db import transaction as db_transaction
from django.db.models import Count, Min, Q
from django.db.models.functions import TruncMinute
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .admin_forms import ComposeForm
from .models import (Notification, NotificationCategory, NotificationPreference,
                     NotificationPriority, PushSubscription)

logger = logging.getLogger(__name__)

PAGE_SIZE = 20
CHUNK = 500            # rows per bulk insert
MAX_PUSH = 2000        # most push jobs queued by one send
DUPLICATE_WINDOW = timedelta(minutes=10)
CLEANUP_DAYS = [7, 14, 30, 60, 90]  # never below a week, so a fresh alert is never swept away

staff_required = user_passes_test(lambda u: u.is_active and u.is_staff)


# --------------------------------------------------------------------------- helpers
def _next(request, fallback):
    target = request.POST.get('next') or request.GET.get('next') or ''
    if target and url_has_allowed_host_and_scheme(
            target, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return target
    return reverse(fallback)


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


def _audience_qs(audience, form=None):
    """Active users in an audience group. Imports are lazy so this app works without Dashboard."""
    users = User.objects.filter(is_active=True)
    if audience == 'staff':
        return users.filter(is_staff=True)
    if audience == 'affiliates':
        return users.filter(affiliate__status='active')
    if audience == 'pro':
        return users.filter(account__status__tier_type__in=['pro', 'enterprise'])
    if audience == 'users':
        return users.filter(pk__in=[u.pk for u in (form.users if form else [])])
    return users


def _respect_preferences(users, category):
    """Drop users who switched this category off, exactly as create_notification() does."""
    prefix = 'notification_preferences__'
    if category == NotificationCategory.REVIEW:
        return users.exclude(**{prefix + 'review_notifications': False})
    if category == NotificationCategory.SAVES:
        return users.exclude(**{prefix + 'save_notifications': False})
    if category == NotificationCategory.MILESTONES:
        return users.exclude(**{prefix + 'milestone_achievements': False})
    if category == NotificationCategory.SYSTEM:
        return users.exclude(**{prefix + 'system_notifications': False})
    if category == NotificationCategory.NEWS:
        return users.exclude(**{prefix + 'price_drop_alerts': False})
    if category == NotificationCategory.ALERTS:
        return users.exclude(**{prefix + 'deletion_warnings': False, prefix + 'stock_alerts': False})
    return users  # announcements always go out


def _queue_pushes(user_ids, title, message, url):
    """One push job per user who has an active browser subscription and push switched on."""
    from django_q.tasks import async_task
    ids = (PushSubscription.objects.filter(active=True, user_id__in=user_ids)
           .exclude(user__notification_preferences__push_notifications=False)
           .values_list('user_id', flat=True).distinct())
    ids = list(ids)[:MAX_PUSH]
    for uid in ids:
        async_task('Notifications.tasks.dispatch_push_notifications', uid, title, message, url or None, None, 'broadcast')
    return len(ids)


# =========================================================================== compose + sent history
def _recent_sends():
    """Group notifications that share title, message and minute. Two or more means a broadcast."""
    since = timezone.now() - timedelta(days=30)
    rows = (Notification.objects.filter(created_at__gte=since)
            .annotate(minute=TruncMinute('created_at'))
            .values('title', 'message', 'category', 'priority', 'minute')
            .annotate(n=Count('id'), n_read=Count('id', filter=Q(is_read=True)), rep_id=Min('id'))
            .filter(n__gte=2).order_by('-minute')[:15])
    return list(rows)


@staff_required
def compose(request):
    allow_all = request.user.is_superuser
    if request.method == 'POST':
        form = ComposeForm(request.POST, allow_all=allow_all)
        if form.is_valid():
            return _send(request, form)
        messages.error(request, 'Fix the highlighted fields and send again.')
    else:
        form = ComposeForm(allow_all=allow_all, initial={'usernames': request.GET.get('to', '')})

    counts = {key: _audience_qs(key).count() for key in ('affiliates', 'pro', 'staff')}
    if allow_all:
        counts['all'] = User.objects.filter(is_active=True).count()
    return render(request, 'admin/notif_compose.html', {
        'form': form, 'counts': counts, 'allow_all': allow_all, 'sends': _recent_sends(),
        'next_url': reverse('notif_admin_compose'),
    })


def _send(request, form):
    d = form.cleaned_data
    now = timezone.now()
    # A refresh or double click would send the same text twice, so refuse an identical send within ten minutes.
    if Notification.objects.filter(title=d['title'], message=d['message'],
                                   created_at__gte=now - DUPLICATE_WINDOW).exists():
        form.add_error('title', 'This exact title and message went out in the last 10 minutes. Change the wording if you mean to send it again.')
        messages.error(request, 'Looks like a duplicate of a send from the last 10 minutes. Nothing was sent.')
        return render(request, 'admin/notif_compose.html', {
            'form': form, 'counts': {}, 'allow_all': request.user.is_superuser, 'sends': _recent_sends(),
            'next_url': reverse('notif_admin_compose'),
        })

    audience = _audience_qs(d['audience'], form)
    total = audience.count()
    receiving = _respect_preferences(audience, d['category'])
    ids = list(receiving.values_list('pk', flat=True))
    skipped = total - len(ids)

    with db_transaction.atomic():
        batch = []
        for uid in ids:
            batch.append(Notification(
                recipient_id=uid, title=d['title'], message=d['message'], category=d['category'],
                priority=d['priority'], action_url=d['action_url'] or None,
                action_text=(d['action_text'] or '').strip() or None))
            if len(batch) >= CHUNK:
                Notification.objects.bulk_create(batch)
                batch = []
        if batch:
            Notification.objects.bulk_create(batch)

    pushed = 0
    if d['push'] and ids:
        try:
            pushed = _queue_pushes(ids, d['title'], d['message'], d['action_url'])
        except Exception:
            logger.exception('Could not queue broadcast pushes')
            messages.warning(request, 'The notifications were saved, but the push jobs could not be queued. See the server log.')
    logger.info('Staff %s sent "%s" to %s users (%s skipped, %s push)', request.user.pk, d['title'], len(ids), skipped, pushed)

    msg = f'Sent to {len(ids)} user{"s" if len(ids) != 1 else ""}.'
    if skipped:
        msg += f' {skipped} skipped because they turned this category off.'
    if d['push']:
        msg += f' {pushed} push alert{"s" if pushed != 1 else ""} queued.'
    messages.success(request, msg)
    return redirect('notif_admin_compose')


@staff_required
@require_POST
def withdraw(request, pk):
    """Delete every copy of a broadcast: same title, message and minute as the one picked."""
    sample = get_object_or_404(Notification, pk=pk)
    start = sample.created_at.replace(second=0, microsecond=0)
    qs = Notification.objects.filter(title=sample.title, message=sample.message,
                                     created_at__gte=start, created_at__lt=start + timedelta(minutes=1))
    count = qs.count()
    qs.delete()
    logger.info('Staff %s withdrew broadcast "%s" (%s copies)', request.user.pk, sample.title, count)
    messages.success(request, f'Withdrawn: {count} cop{"ies" if count != 1 else "y"} deleted. Push alerts already delivered cannot be recalled.')
    return redirect(_next(request, 'notif_admin_compose'))


# =========================================================================== browse
@staff_required
def notification_list(request):
    q = (request.GET.get('q') or '').strip()
    category = request.GET.get('category', '')
    state = request.GET.get('state', '')
    priority = request.GET.get('priority', '')

    qs = Notification.objects.select_related('recipient', 'content_type')
    if category in dict(NotificationCategory.choices):
        qs = qs.filter(category=category)
    else:
        category = ''
    if state == 'unread':
        qs = qs.filter(is_read=False)
    elif state == 'read':
        qs = qs.filter(is_read=True)
    else:
        state = ''
    if priority in dict(NotificationPriority.choices):
        qs = qs.filter(priority=priority)
    else:
        priority = ''
    if q:
        qs = qs.filter(Q(recipient__username__icontains=q) | Q(title__icontains=q) | Q(message__icontains=q))

    return render(request, 'admin/notif_list.html', {
        'page_obj': _paginate(request, qs.order_by('-created_at')), 'keep': _keep(request),
        'q': q, 'category': category, 'state': state, 'priority': priority,
        'categories': NotificationCategory.choices, 'priorities': NotificationPriority.choices,
        'total': Notification.objects.count(), 'next_url': request.get_full_path(),
    })


@staff_required
@require_POST
def notification_delete(request, pk):
    n = get_object_or_404(Notification, pk=pk)
    n.delete()
    messages.success(request, 'Notification deleted.')
    return redirect(_next(request, 'notif_admin_list'))


# =========================================================================== overview + tools
def _optouts():
    """How many users switched each preference off, out of everyone who has a preferences row."""
    total = NotificationPreference.objects.count()
    labels = [
        ('review_notifications', 'Reviews'), ('save_notifications', 'Saves'),
        ('view_milestone_notifications', 'View milestones'), ('system_notifications', 'System'),
        ('deletion_warnings', 'Expiry warnings'), ('stock_alerts', 'Stock alerts'),
        ('transaction_notifications', 'Money activity'), ('price_drop_alerts', 'Price drops'),
        ('reply_notifications', 'Review replies'), ('report_notifications', 'Reports on listings'),
        ('milestone_achievements', 'Achievements'), ('push_notifications', 'Push alerts'),
    ]
    agg = NotificationPreference.objects.aggregate(**{f'n_{f}': Count('id', filter=Q(**{f: False})) for f, _ in labels})
    rows = [{'label': label, 'off': agg[f'n_{f}'], 'pct': round(agg[f'n_{f}'] * 100 / total) if total else 0}
            for f, label in labels]
    rows.sort(key=lambda r: -r['off'])
    email_on = NotificationPreference.objects.filter(email_notifications=True).count()
    return total, rows, email_on


@staff_required
def overview(request):
    now = timezone.now()
    stats = Notification.objects.aggregate(
        total=Count('id'), unread=Count('id', filter=Q(is_read=False)),
        last_day=Count('id', filter=Q(created_at__gte=now - timedelta(days=1))),
        last_week=Count('id', filter=Q(created_at__gte=now - timedelta(days=7))),
    )
    sweeps = []
    cutoffs = {d: now - timedelta(days=d) for d in CLEANUP_DAYS}
    agg = Notification.objects.aggregate(**{
        f'{kind}_{d}': Count('id', filter=Q(created_at__lte=cutoffs[d], **({'is_read': True} if kind == 'read' else {})))
        for d in CLEANUP_DAYS for kind in ('read', 'all')})
    for d in CLEANUP_DAYS:
        sweeps.append({'days': d, 'read': agg[f'read_{d}'], 'all': agg[f'all_{d}']})

    pref_total, optouts, email_on = _optouts()
    push = PushSubscription.objects.aggregate(
        n_active=Count('id', filter=Q(active=True)),
        n_users=Count('user', filter=Q(active=True), distinct=True))
    mine = PushSubscription.objects.filter(user=request.user, active=True).count()
    return render(request, 'admin/notif_overview.html', {
        'stats': stats, 'read_pct': round((stats['total'] - stats['unread']) * 100 / stats['total']) if stats['total'] else 0,
        'sweeps': sweeps, 'pref_total': pref_total, 'optouts': optouts, 'email_on': email_on,
        'push': push, 'my_subs': mine, 'next_url': reverse('notif_admin_overview'),
    })


@staff_required
@require_POST
def cleanup(request):
    try:
        days = int(request.POST.get('days', ''))
    except ValueError:
        days = 0
    if days not in CLEANUP_DAYS:
        messages.error(request, 'Pick one of the listed ages.')
        return redirect('notif_admin_overview')
    scope = request.POST.get('scope', 'read')
    qs = Notification.objects.filter(created_at__lte=timezone.now() - timedelta(days=days))
    if scope != 'all':
        qs = qs.filter(is_read=True)
    deleted = qs.delete()[0]
    logger.info('Staff %s cleaned notifications older than %s days (%s): %s deleted', request.user.pk, days, scope, deleted)
    messages.success(request, f'Deleted {deleted} notification{"s" if deleted != 1 else ""} older than {days} days.')
    return redirect('notif_admin_overview')


@staff_required
@require_POST
def test_push(request):
    """Send one push to the signed-in staff member, to check VAPID keys and the queue worker."""
    if not PushSubscription.objects.filter(user=request.user, active=True).exists():
        messages.error(request, 'This account has no active push subscription. Allow notifications in your browser on the site first.')
        return redirect('notif_admin_overview')
    try:
        from django_q.tasks import async_task
        async_task('Notifications.tasks.dispatch_push_notifications', request.user.pk,
                   'Test from OpenSell admin', 'If you can read this, push works.', '/', None, 'admin-test')
    except Exception:
        logger.exception('Test push could not be queued')
        messages.error(request, 'Could not queue the push job. Is django-q running?')
        return redirect('notif_admin_overview')
    messages.success(request, 'Test push queued. It should arrive within a few seconds. If it does not, check the django-q worker and the VAPID keys.')
    return redirect('notif_admin_overview')
