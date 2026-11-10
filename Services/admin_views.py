"""
Staff pages for the Services app: moderate listings, watch inquiries, remove abusive reviews,
and run the expiry tools. Reports themselves stay on the existing 'admin_reports' pages.

Every view is staff-only and every change is a POST.
"""
import logging
import uuid
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.contrib.contenttypes.models import ContentType
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Avg, Count, Prefetch, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from User.models import ItemReport

from .models import (ServiceImage, ServiceInquiry, ServiceListing, ServiceReview,
                     ServiceReviewReply)

logger = logging.getLogger(__name__)

PAGE_SIZE = 20
EXPIRY_WINDOW_DAYS = 7      # "expiring soon" matches the 1, 3 and 7 day warnings the model sends
OPEN_REPORT = ('pending', 'reviewing')
TOOL_CAP = 200              # most listings one expiry sweep deletes, so the request cannot time out
WARN_CAP = 500
RESCORE_CAP = 5000
CATEGORIES = dict(ServiceListing.SERVICE_CATEGORIES)
ACTIVE_INQUIRY = ('pending', 'responded', 'negotiating')

staff_required = user_passes_test(lambda u: u.is_active and u.is_staff)


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
    return (request.POST.get('reason') or '').strip()[:limit]


def _service_ct():
    return ContentType.objects.get_for_model(ServiceListing)


def _as_uuid(value):
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return None


def _open_report_ids():
    """Ids of services that have at least one unresolved report."""
    raw = (ItemReport.objects.filter(content_type=_service_ct(), status__in=OPEN_REPORT)
           .order_by().values_list('object_id', flat=True).distinct())
    return {u for u in map(_as_uuid, raw) if u}


def _report_counts(service_ids):
    """{uuid: {'open': n, 'all': n}} for the given services, in one query."""
    out = {}
    wanted = [str(i) for i in service_ids]
    if not wanted:
        return out
    rows = (ItemReport.objects.filter(content_type=_service_ct(), object_id__in=wanted)
            .order_by().values('object_id')
            .annotate(n_all=Count('id'), n_open=Count('id', filter=Q(status__in=OPEN_REPORT))))
    for r in rows:
        key = _as_uuid(r['object_id'])
        if key:
            out[key] = {'open': r['n_open'], 'all': r['n_all']}
    return out


def _state(s, now):
    """One label for a listing: what a visitor would actually see."""
    if s.is_suspended:
        return 'suspended', 'Suspended'
    if not s.is_active:
        return 'hidden', 'Hidden'
    if s.expiration_date and s.expiration_date <= now:
        return 'expired', 'Expired'
    if s.expiration_date and s.expiration_date <= now + timedelta(days=EXPIRY_WINDOW_DAYS):
        return 'expiring', 'Expiring soon'
    return 'active', 'Active'


def _cover(service):
    imgs = list(service.images.all())
    cover = next((i for i in imgs if i.is_primary), imgs[0] if imgs else None)
    try:
        return cover.image.url if cover else ''
    except Exception:
        return ''


def _rescore(service):
    """Recompute the ranking score after something that feeds it (a review) changed."""
    try:
        ServiceListing.objects.filter(pk=service.pk).update(boost_score=service.calculate_boost_score())
    except Exception:
        logger.warning('Could not rescore service %s', service.pk, exc_info=True)


def services_admin_stats():
    """Counts for the panel links and tab badges. Merge into the admin_panel context."""
    now = timezone.now()
    row = ServiceListing.objects.aggregate(
        n_all=Count('id'),
        n_suspended=Count('id', filter=Q(is_suspended=True)),
        n_expired=Count('id', filter=Q(expiration_date__lte=now)),
    )
    return {
        'services_total': row['n_all'],
        'services_suspended': row['n_suspended'],
        'services_expired': row['n_expired'],
        'services_open_reports': len(_open_report_ids()),
        'services_pending_inquiries': ServiceInquiry.objects.filter(status='pending').count(),
    }


# =========================================================================== listings
STATUS_TABS = ('all', 'active', 'suspended', 'hidden', 'featured', 'expiring', 'expired', 'reported')


@staff_required
def listing_list(request):
    now = timezone.now()
    soon = now + timedelta(days=EXPIRY_WINDOW_DAYS)
    status = request.GET.get('status', 'all')
    if status not in STATUS_TABS:
        status = 'all'
    category = request.GET.get('category', '')
    if category not in CATEGORIES:
        category = ''
    q = (request.GET.get('q') or '').strip()

    base = ServiceListing.objects.all()
    counts = base.aggregate(
        n_all=Count('id'),
        n_active=Count('id', filter=Q(is_active=True, is_suspended=False)),
        n_suspended=Count('id', filter=Q(is_suspended=True)),
        n_hidden=Count('id', filter=Q(is_active=False, is_suspended=False)),
        n_featured=Count('id', filter=Q(is_featured=True)),
        n_expiring=Count('id', filter=Q(expiration_date__gt=now, expiration_date__lte=soon)),
        n_expired=Count('id', filter=Q(expiration_date__lte=now)),
    )
    reported_ids = _open_report_ids()
    counts['n_reported'] = len(reported_ids)

    qs = (base.select_related('provider__user', 'suspended_by')
          .prefetch_related(Prefetch('images', queryset=ServiceImage.objects.only('id', 'service_id', 'image', 'is_primary')))
          .annotate(avg_stars=Avg('reviews__rating'), n_reviews=Count('reviews', distinct=True))
          .order_by('-created_at'))
    if status == 'active':
        qs = qs.filter(is_active=True, is_suspended=False)
    elif status == 'suspended':
        qs = qs.filter(is_suspended=True).order_by('-suspended_at')
    elif status == 'hidden':
        qs = qs.filter(is_active=False, is_suspended=False)
    elif status == 'featured':
        qs = qs.filter(is_featured=True)
    elif status == 'expiring':
        qs = qs.filter(expiration_date__gt=now, expiration_date__lte=soon).order_by('expiration_date')
    elif status == 'expired':
        qs = qs.filter(expiration_date__lte=now).order_by('expiration_date')
    elif status == 'reported':
        qs = qs.filter(pk__in=reported_ids)
    if category:
        qs = qs.filter(category=category)
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(provider__user__username__icontains=q)
                       | Q(provider__user__email__icontains=q))

    page = _paginate(request, qs)
    reports = _report_counts([s.pk for s in page.object_list])
    for s in page.object_list:
        s.state, s.state_label = _state(s, now)
        s.cover_url = _cover(s)
        s.reports = reports.get(s.pk, {'open': 0, 'all': 0})
    return render(request, 'admin/svc_list.html', {
        'page_obj': page, 'keep': _keep(request), 'status': status, 'q': q, 'category': category,
        'categories': ServiceListing.SERVICE_CATEGORIES, 'counts': counts,
        'next_url': request.get_full_path(),
    })


@staff_required
def listing_detail(request, pk):
    now = timezone.now()
    s = get_object_or_404(
        ServiceListing.objects.select_related('provider__user', 'suspended_by', 'location'), pk=pk)
    s.state, s.state_label = _state(s, now)
    reports = list(ItemReport.objects.filter(content_type=_service_ct(), object_id=str(s.pk))
                   .select_related('reviewed_by').order_by('-reported_at')[:20])
    inq_rows = s.inquiries.values('status').annotate(n=Count('id'))
    inq_by_status = {r['status']: r['n'] for r in inq_rows}
    inquiries = list(s.inquiries.select_related('client__user').order_by('-created_at')[:8])
    reviews = list(s.reviews.select_related('reviewer')
                   .prefetch_related(Prefetch('replies', queryset=ServiceReviewReply.objects.select_related('replier')))
                   .order_by('-created_at')[:8])
    rating = s.reviews.aggregate(avg=Avg('rating'), n=Count('id'))
    return render(request, 'admin/svc_detail.html', {
        's': s, 'reports': reports, 'open_reports': sum(1 for r in reports if r.status in OPEN_REPORT),
        'inquiries': inquiries, 'inq_total': sum(inq_by_status.values()), 'inq_by_status': inq_by_status,
        'reviews': reviews, 'rating': rating,
        'images': list(s.images.all()), 'documents': list(s.documents.all()),
        'category_label': CATEGORIES.get(s.category, s.category),
        'next_url': request.get_full_path(),
    })


def _resolve_open_reports(service, staff, note):
    return ItemReport.objects.filter(
        content_type=_service_ct(), object_id=str(service.pk), status__in=OPEN_REPORT,
    ).update(status='resolved', reviewed_by=staff, reviewed_at=timezone.now(), resolution_notes=note)


@staff_required
@require_POST
def listing_suspend(request, pk):
    s = get_object_or_404(ServiceListing.objects.select_related('provider__user'), pk=pk)
    reason = _reason(request)
    if not reason:
        messages.error(request, 'A reason is required. The provider receives it by email.')
    elif s.is_suspended:
        messages.info(request, 'That service is already suspended.')
    else:
        email_failed = False
        try:
            s.suspend(request.user, reason)
        except Exception:
            # suspend() saves first and emails second, so a broken email template must not undo it
            email_failed = True
            logger.exception('Suspension email failed for service %s', s.pk)
        s.refresh_from_db(fields=['is_suspended'])
        if not s.is_suspended:
            messages.error(request, 'Could not suspend that service. Nothing changed.')
        else:
            closed = _resolve_open_reports(s, request.user, f'Service suspended by {request.user.username}')
            note = f' {closed} open report{"s" if closed != 1 else ""} marked resolved.' if closed else ''
            messages.success(request, f'"{s.title}" suspended.{note}')
            if email_failed:
                messages.warning(request, 'The provider could not be emailed. Check the email template and settings.')
    return redirect(_next(request, 'svc_admin_list'))


@staff_required
@require_POST
def listing_unsuspend(request, pk):
    s = get_object_or_404(ServiceListing.objects.select_related('provider__user'), pk=pk)
    if not s.is_suspended:
        messages.info(request, 'That service is not suspended.')
    else:
        email_failed = False
        try:
            s.unsuspend()
        except Exception:
            email_failed = True
            logger.exception('Reinstatement email failed for service %s', s.pk)
        s.refresh_from_db(fields=['is_suspended'])
        if s.is_suspended:
            messages.error(request, 'Could not reinstate that service. Nothing changed.')
        else:
            messages.success(request, f'"{s.title}" reinstated.')
            if email_failed:
                messages.warning(request, 'The provider could not be emailed. Check the email template and settings.')
    return redirect(_next(request, 'svc_admin_list'))


@staff_required
@require_POST
def listing_feature(request, pk):
    s = get_object_or_404(ServiceListing, pk=pk)
    on = request.POST.get('to') == 'on'
    ServiceListing.objects.filter(pk=s.pk).update(is_featured=on)
    messages.success(request, f'"{s.title}" is {"now" if on else "no longer"} featured.')
    return redirect(_next(request, 'svc_admin_list'))


@staff_required
@require_POST
def listing_activate(request, pk):
    s = get_object_or_404(ServiceListing, pk=pk)
    on = request.POST.get('to') == 'on'
    ServiceListing.objects.filter(pk=s.pk).update(is_active=on)
    messages.success(request, f'"{s.title}" is {"visible again" if on else "hidden from the site"}.')
    return redirect(_next(request, 'svc_admin_list'))


@staff_required
@require_POST
def listing_delete(request, pk):
    s = get_object_or_404(ServiceListing.objects.select_related('provider__user'), pk=pk)
    title = s.title
    logger.info('Staff %s deleted service %s (%s). Reason: %s',
                request.user.pk, s.pk, title, _reason(request) or 'none given')
    try:
        s.delete()
    except Exception:
        logger.exception('Could not delete service %s', pk)
        messages.error(request, 'Could not delete that service. Nothing was removed.')
        return redirect(_next(request, 'svc_admin_list'))
    messages.success(request, f'"{title}" deleted.')
    # the detail page no longer exists, so never bounce back to it
    target = _next(request, 'svc_admin_list')
    return redirect('svc_admin_list' if str(pk) in target else target)


# =========================================================================== inquiries
INQUIRY_STATUSES = ServiceInquiry.INQUIRY_STATUS


@staff_required
def inquiry_list(request):
    status = request.GET.get('status', 'all')
    if status not in dict(INQUIRY_STATUSES):
        status = 'all'
    q = (request.GET.get('q') or '').strip()
    service_id = _as_uuid(request.GET.get('service'))

    counts = ServiceInquiry.objects.aggregate(
        n_all=Count('id'),
        n_pending=Count('id', filter=Q(status='pending')),
        n_responded=Count('id', filter=Q(status='responded')),
        n_negotiating=Count('id', filter=Q(status='negotiating')),
    )
    qs = ServiceInquiry.objects.select_related('service', 'client__user', 'service__provider__user')
    if status != 'all':
        qs = qs.filter(status=status)
    if service_id:
        qs = qs.filter(service_id=service_id)
    if q:
        qs = qs.filter(Q(service__title__icontains=q) | Q(client__user__username__icontains=q)
                       | Q(service__provider__user__username__icontains=q) | Q(message__icontains=q))
    page = _paginate(request, qs.order_by('-created_at'))
    return render(request, 'admin/svc_inquiries.html', {
        'page_obj': page, 'keep': _keep(request), 'status': status, 'q': q, 'counts': counts,
        'statuses': INQUIRY_STATUSES, 'service_id': service_id or '', 'active_states': ACTIVE_INQUIRY,
        'next_url': request.get_full_path(),
    })


@staff_required
@require_POST
def inquiry_cancel(request, pk):
    inq = get_object_or_404(ServiceInquiry.objects.select_related('service'), pk=pk)
    reason = _reason(request)
    if inq.status not in ACTIVE_INQUIRY:
        messages.info(request, 'Only open inquiries can be cancelled.')
    elif not reason:
        messages.error(request, 'A reason is required. It is kept in the server log.')
    else:
        inq.status = 'cancelled'
        inq.save(update_fields=['status', 'updated_at'])
        logger.info('Staff %s cancelled inquiry %s. Reason: %s', request.user.pk, inq.pk, reason)
        messages.success(request, 'Inquiry cancelled. The client can send a new one.')
    return redirect(_next(request, 'svc_admin_inquiries'))


# =========================================================================== reviews
BANDS = {'low': (1, 2), 'mid': (3, 3), 'high': (4, 5)}


@staff_required
def review_list(request):
    band = request.GET.get('band', 'all')
    if band not in BANDS:
        band = 'all'
    q = (request.GET.get('q') or '').strip()
    service_id = _as_uuid(request.GET.get('service'))

    counts = ServiceReview.objects.aggregate(
        n_all=Count('id'),
        n_low=Count('id', filter=Q(rating__lte=2)),
        n_mid=Count('id', filter=Q(rating=3)),
        n_high=Count('id', filter=Q(rating__gte=4)),
    )
    qs = (ServiceReview.objects.select_related('reviewer', 'service')
          .prefetch_related(Prefetch('replies', queryset=ServiceReviewReply.objects.select_related('replier').order_by('created_at'))))
    if band in BANDS:
        lo, hi = BANDS[band]
        qs = qs.filter(rating__gte=lo, rating__lte=hi)
    if service_id:
        qs = qs.filter(service_id=service_id)
    if q:
        qs = qs.filter(Q(review_text__icontains=q) | Q(reviewer__username__icontains=q) | Q(service__title__icontains=q))
    page = _paginate(request, qs.order_by('-created_at'))
    return render(request, 'admin/svc_reviews.html', {
        'page_obj': page, 'keep': _keep(request), 'band': band, 'q': q, 'counts': counts,
        'service_id': service_id or '', 'next_url': request.get_full_path(),
    })


@staff_required
@require_POST
def review_delete(request, pk):
    r = get_object_or_404(ServiceReview.objects.select_related('service__provider__user'), pk=pk)
    service = r.service
    logger.info('Staff %s deleted service review %s by %s. Reason: %s',
                request.user.pk, r.pk, r.reviewer_id, _reason(request) or 'none given')
    r.delete()           # replies go with it
    _rescore(service)
    messages.success(request, 'Review deleted. The service ranking was recalculated.')
    return redirect(_next(request, 'svc_admin_reviews'))


@staff_required
@require_POST
def reply_delete(request, pk):
    reply = get_object_or_404(ServiceReviewReply, pk=pk)
    logger.info('Staff %s deleted service review reply %s. Reason: %s',
                request.user.pk, reply.pk, _reason(request) or 'none given')
    reply.delete()
    messages.success(request, 'Reply deleted.')
    return redirect(_next(request, 'svc_admin_reviews'))


# =========================================================================== overview and tools
@staff_required
def overview(request):
    now = timezone.now()
    since = now - timedelta(days=30)
    soon = now + timedelta(days=EXPIRY_WINDOW_DAYS)

    stats = ServiceListing.objects.aggregate(
        n_all=Count('id'),
        n_live=Count('id', filter=Q(is_active=True, is_suspended=False)),
        n_suspended=Count('id', filter=Q(is_suspended=True)),
        n_hidden=Count('id', filter=Q(is_active=False, is_suspended=False)),
        n_featured=Count('id', filter=Q(is_featured=True)),
        n_expiring=Count('id', filter=Q(expiration_date__gt=now, expiration_date__lte=soon)),
        n_expired=Count('id', filter=Q(expiration_date__lte=now)),
        n_new=Count('id', filter=Q(created_at__gte=since)),
        total_views=Sum('view_count'),
    )
    stats['total_views'] = stats['total_views'] or 0

    # categories, live listings only
    cat_rows = (ServiceListing.objects.filter(is_active=True, is_suspended=False)
                .values('category').annotate(n=Count('id'), n_providers=Count('provider', distinct=True)))
    by_cat = {r['category']: r for r in cat_rows}
    top = max([r['n'] for r in by_cat.values()] or [1])
    categories = []
    for key, label in ServiceListing.SERVICE_CATEGORIES:
        r = by_cat.get(key, {'n': 0, 'n_providers': 0})
        categories.append({'label': label, 'n': r['n'], 'providers': r['n_providers'],
                           'pct': round(r['n'] * 100 / top) if top else 0})

    # inquiries
    inq_rows = ServiceInquiry.objects.values('status').annotate(n=Count('id'))
    inq_map = {r['status']: r['n'] for r in inq_rows}
    inq_total = sum(inq_map.values())
    inq_top = max(inq_map.values() or [1])
    inquiries = [{'label': label, 'n': inq_map.get(key, 0),
                  'pct': round(inq_map.get(key, 0) * 100 / inq_top) if inq_top else 0}
                 for key, label in INQUIRY_STATUSES]
    inq_new = ServiceInquiry.objects.filter(created_at__gte=since).count()

    # reviews
    rv = ServiceReview.objects.aggregate(avg=Avg('rating'), n=Count('id'),
                                         n_new=Count('id', filter=Q(created_at__gte=since)))
    dist_rows = ServiceReview.objects.values('rating').annotate(n=Count('id'))
    dist_map = {r['rating']: r['n'] for r in dist_rows}
    dist_top = max(dist_map.values() or [1])
    distribution = [{'stars': s, 'n': dist_map.get(s, 0),
                     'pct': round(dist_map.get(s, 0) * 100 / dist_top) if dist_top else 0}
                    for s in (5, 4, 3, 2, 1)]

    public = ServiceListing.objects.filter(is_active=True, is_suspended=False).select_related('provider__user')
    top_viewed = list(public.order_by('-view_count')[:5])
    top_inquired = list(public.order_by('-inquiry_count')[:5])

    return render(request, 'admin/svc_overview.html', {
        'stats': stats, 'categories': categories, 'inquiries': inquiries, 'inq_total': inq_total,
        'inq_new': inq_new, 'rv': rv, 'distribution': distribution,
        'top_viewed': top_viewed, 'top_inquired': top_inquired,
        'open_reports': len(_open_report_ids()),
        'warn_due': _warning_candidates(now).count(),
        'next_url': request.get_full_path(),
    })


def _warning_candidates(now):
    return ServiceListing.objects.filter(
        is_active=True, is_suspended=False, deletion_warning_sent=False,
        expiration_date__gt=now, expiration_date__lte=now + timedelta(days=EXPIRY_WINDOW_DAYS))


@staff_required
@require_POST
def tool_run(request, action):
    now = timezone.now()
    back = _next(request, 'svc_admin_overview')

    if action == 'expired':
        # Suspended listings are kept on purpose: they may be evidence for a report.
        expired = list(ServiceListing.objects.filter(
            is_active=True, is_suspended=False, expiration_date__lte=now)[:TOOL_CAP])
        done = failed = 0
        for s in expired:
            try:
                s.delete()
                done += 1
            except Exception:
                failed += 1
                logger.warning('Could not delete expired service %s', s.pk, exc_info=True)
        logger.info('Staff %s ran the expired-services sweep: %s deleted, %s failed', request.user.pk, done, failed)
        if not expired:
            messages.info(request, 'No expired services to delete.')
        else:
            messages.success(request, f'Deleted {done} expired service{"s" if done != 1 else ""}.')
            if failed:
                messages.warning(request, f'{failed} could not be deleted. See the server log.')
            if len(expired) == TOOL_CAP:
                messages.info(request, f'Stopped at {TOOL_CAP}. Run it again for the rest.')

    elif action == 'warnings':
        sent = 0
        for s in _warning_candidates(now).select_related('provider__user')[:WARN_CAP]:
            s.send_deletion_warning()   # only acts on 1, 3 or 7 days left
            if s.deletion_warning_sent:
                sent += 1
        messages.success(request, f'Sent {sent} expiry warning{"s" if sent != 1 else ""}.') if sent \
            else messages.info(request, 'No service is exactly 1, 3 or 7 days from expiry right now.')

    elif action == 'rescore':
        changed = seen = 0
        qs = ServiceListing.objects.filter(is_suspended=False).select_related('provider__user')
        for s in qs.iterator(chunk_size=200):
            if seen >= RESCORE_CAP:
                break
            seen += 1
            try:
                score = s.calculate_boost_score()
            except Exception:
                continue
            if s.boost_score != score:
                ServiceListing.objects.filter(pk=s.pk).update(boost_score=score)
                changed += 1
        messages.success(request, f'Checked {seen} service{"s" if seen != 1 else ""}, updated {changed} ranking score{"s" if changed != 1 else ""}.')

    else:
        messages.error(request, 'Unknown tool.')
    return redirect(back)
