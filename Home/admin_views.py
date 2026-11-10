"""
Staff pages for the Home app: banners, catalog, listing moderation, review moderation, tools.
Every view is staff-only and every change is a POST (list pages never change data on GET).
"""
import logging
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .admin_forms import (BannerAdminForm, BrandAdminForm, CategoryAdminForm,
                          SubcategoryAdminForm)
from .models import (Banner, Brand, Category, Product_Image, Product_Listing,
                     Review, ReviewReply, Subcategory)

logger = logging.getLogger(__name__)

PAGE_SIZE = 20
EXPIRY_WINDOW_DAYS = 3  # same threshold the seller warning emails use (3 and 1 days)

staff_required = user_passes_test(lambda u: u.is_active and u.is_staff)


# --------------------------------------------------------------------------- helpers
def _next(request, fallback):
    """POSTed or GETed `next`, only if it points back at this site."""
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
    """Query string without `page`, for pager links."""
    q = request.GET.copy()
    q.pop('page', None)
    return q.urlencode()


def _reason(request, limit=500):
    return (request.POST.get('reason') or '').strip()[:limit]


def _banner_state(b, now):
    if not b.is_active:
        return 'off'
    if b.start_date and b.start_date > now:
        return 'scheduled'
    if b.end_date and b.end_date <= now:
        return 'expired'
    return 'live'


STATE_LABEL = {'live': 'Live', 'scheduled': 'Scheduled', 'expired': 'Expired', 'off': 'Switched off'}


def _live_q(now):
    return (Q(is_active=True)
            & (Q(start_date__isnull=True) | Q(start_date__lte=now))
            & (Q(end_date__isnull=True) | Q(end_date__gt=now)))


def home_admin_stats():
    """Counts for the panel links and the tab badges. Four cheap queries."""
    now = timezone.now()
    soon = now + timedelta(days=EXPIRY_WINDOW_DAYS)
    banners = Banner.objects.aggregate(
        total=Count('id'),
        live=Count('id', filter=_live_q(now)),
    )
    listings = Product_Listing.objects.aggregate(
        suspended=Count('id', filter=Q(is_suspended=True)),
        expiring=Count('id', filter=Q(expiration_date__gt=now, expiration_date__lte=soon,
                                      listing_type__in=['standard', 'urgent'])),
        expired=Count('id', filter=Q(expiration_date__lte=now,
                                     listing_type__in=['standard', 'urgent'])),
    )
    return {
        'banners_total': banners['total'],
        'banners_live': banners['live'],
        'listings_suspended': listings['suspended'],
        'listings_expiring': listings['expiring'],
        'listings_expired': listings['expired'],
        'catalog_categories': Category.objects.count(),
        'catalog_brands': Brand.objects.count(),
        'reviews_total': Review.objects.count(),
    }


# --------------------------------------------------------------------------- banners
@staff_required
def banner_list(request):
    now = timezone.now()
    status = request.GET.get('status', 'all')
    location = request.GET.get('location', '')

    base = Banner.objects.all()
    counts = base.aggregate(
        all=Count('id'),
        live=Count('id', filter=_live_q(now)),
        scheduled=Count('id', filter=Q(is_active=True, start_date__gt=now)),
        expired=Count('id', filter=Q(is_active=True, end_date__lte=now)),
        off=Count('id', filter=Q(is_active=False)),
    )

    qs = base
    if status == 'live':
        qs = qs.filter(_live_q(now))
    elif status == 'scheduled':
        qs = qs.filter(is_active=True, start_date__gt=now)
    elif status == 'expired':
        qs = qs.filter(is_active=True, end_date__lte=now)
    elif status == 'off':
        qs = qs.filter(is_active=False)
    else:
        status = 'all'
    if location in dict(Banner.DISPLAY_LOCATIONS):
        qs = qs.filter(display_location=location)
    else:
        location = ''

    page = _paginate(request, qs)
    for b in page.object_list:
        b.state = _banner_state(b, now)
        b.state_label = STATE_LABEL[b.state]

    return render(request, 'admin/home_banners.html', {
        'page_obj': page, 'keep': _keep(request), 'status': status, 'location': location,
        'counts': counts, 'locations': Banner.DISPLAY_LOCATIONS,
        'next_url': request.get_full_path(),
    })


@staff_required
def banner_form(request, pk=None):
    banner = get_object_or_404(Banner, pk=pk) if pk else None
    if request.method == 'POST':
        form = BannerAdminForm(request.POST, request.FILES, instance=banner)
        if form.is_valid():
            form.save()
            messages.success(request, 'Banner saved.' if banner else 'Banner added.')
            return redirect(_next(request, 'home_admin_banners') if banner else 'home_admin_banners')
        messages.error(request, 'Fix the highlighted fields and save again.')
    else:
        form = BannerAdminForm(instance=banner)
    return render(request, 'admin/home_banner_form.html', {
        'form': form, 'banner': banner, 'next_url': _next(request, 'home_admin_banners'),
    })


@staff_required
@require_POST
def banner_toggle(request, pk):
    banner = get_object_or_404(Banner, pk=pk)
    banner.is_active = not banner.is_active
    banner.save(update_fields=['is_active', 'updated_at'])
    messages.success(request, 'Banner switched on.' if banner.is_active else 'Banner switched off.')
    return redirect(_next(request, 'home_admin_banners'))


@staff_required
@require_POST
def banner_delete(request, pk):
    banner = get_object_or_404(Banner, pk=pk)
    files = [f for f in (banner.image, banner.mobile_image) if f]
    banner.delete()
    for f in files:
        try:
            f.delete(save=False)
        except Exception:
            logger.warning('Could not remove banner file %s', f.name)
    messages.success(request, 'Banner deleted.')
    return redirect(_next(request, 'home_admin_banners'))


# --------------------------------------------------------------------------- catalog
CATALOG = {
    'categories': {'model': Category, 'form': CategoryAdminForm, 'noun': 'category', 'plural': 'Categories'},
    'subcategories': {'model': Subcategory, 'form': SubcategoryAdminForm, 'noun': 'subcategory', 'plural': 'Subcategories'},
    'brands': {'model': Brand, 'form': BrandAdminForm, 'noun': 'brand', 'plural': 'Brands'},
}


def _catalog_or_404(kind):
    if kind not in CATALOG:
        from django.http import Http404
        raise Http404
    return CATALOG[kind]


@staff_required
def catalog_list(request):
    tab = request.GET.get('tab', 'categories')
    if tab not in CATALOG:
        tab = 'categories'
    q = (request.GET.get('q') or '').strip()
    category_id = request.GET.get('category', '')

    if tab == 'categories':
        qs = (Category.objects.annotate(n_products=Count('product_listing', distinct=True),
                                        n_subs=Count('subcategories', distinct=True))
              .order_by('name'))
    elif tab == 'subcategories':
        qs = (Subcategory.objects.select_related('category')
              .annotate(n_products=Count('products', distinct=True))
              .order_by('category__name', 'name'))
        if category_id.isdigit():
            qs = qs.filter(category_id=category_id)
        else:
            category_id = ''
    else:
        qs = (Brand.objects.annotate(n_products=Count('products', distinct=True))
              .prefetch_related('categories').order_by('name'))
    if q:
        qs = qs.filter(name__icontains=q)

    return render(request, 'admin/home_catalog.html', {
        'tab': tab, 'q': q, 'category_id': category_id, 'page_obj': _paginate(request, qs),
        'keep': _keep(request), 'tabs': [(k, v['plural']) for k, v in CATALOG.items()],
        'tab_counts': {'categories': Category.objects.count(),
                       'subcategories': Subcategory.objects.count(),
                       'brands': Brand.objects.count()},
        'categories': Category.objects.order_by('name'),
        'next_url': request.get_full_path(),
    })


@staff_required
def catalog_form(request, kind, pk=None):
    cfg = _catalog_or_404(kind)
    obj = get_object_or_404(cfg['model'], pk=pk) if pk else None
    if request.method == 'POST':
        form = cfg['form'](request.POST, request.FILES, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, f"{cfg['noun'].capitalize()} saved.")
            return redirect(f"{reverse('home_admin_catalog')}?tab={kind}")
        messages.error(request, 'Fix the highlighted fields and save again.')
    else:
        initial = {}
        if not obj and kind == 'subcategories' and request.GET.get('category', '').isdigit():
            initial['category'] = request.GET['category']
        form = cfg['form'](instance=obj, initial=initial)
    return render(request, 'admin/home_catalog_form.html', {
        'form': form, 'obj': obj, 'kind': kind, 'noun': cfg['noun'], 'plural': cfg['plural'],
    })


@staff_required
@require_POST
def catalog_delete(request, kind, pk):
    cfg = _catalog_or_404(kind)
    obj = get_object_or_404(cfg['model'], pk=pk)
    back = _next(request, 'home_admin_catalog')

    # Category.on_delete is CASCADE on Product_Listing, so a category with listings
    # would silently wipe those listings. Block it, and block anything still in use.
    if kind == 'categories':
        n_products = Product_Listing.objects.filter(category=obj).count()
        n_subs = obj.subcategories.count()
        if n_products or n_subs:
            messages.error(request, f'"{obj.name}" still has {n_products} listing(s) and {n_subs} subcategory(ies). '
                                    'Move or remove them first.')
            return redirect(back)
    elif kind == 'subcategories':
        n_products = obj.products.count()
        if n_products:
            messages.error(request, f'"{obj.name}" still has {n_products} listing(s). Move them first.')
            return redirect(back)

    name = str(obj.name)
    image = getattr(obj, 'image', None)
    obj.delete()
    if image:
        try:
            image.delete(save=False)
        except Exception:
            logger.warning('Could not remove file for %s', name)
    messages.success(request, f'Deleted "{name}".')
    return redirect(back)


# --------------------------------------------------------------------------- listings
def _attach_cover(items, now):
    for p in items:
        if p.is_suspended:
            p.state, p.state_label = 'suspended', 'Suspended'
        elif p.listing_type != 'permanent' and p.expiration_date and p.expiration_date <= now:
            p.state, p.state_label = 'expired', 'Expired'
        elif p.listing_type != 'permanent' and p.expiration_date and p.expiration_date <= now + timedelta(days=EXPIRY_WINDOW_DAYS):
            p.state, p.state_label = 'expiring', 'Expiring soon'
        else:
            p.state, p.state_label = 'active', 'Active'
        imgs = list(p.images.all())
        cover = next((i for i in imgs if i.is_primary), imgs[0] if imgs else None)
        try:
            p.cover_url = cover.image.url if cover else ''
        except Exception:
            p.cover_url = ''


@staff_required
def listing_list(request):
    now = timezone.now()
    soon = now + timedelta(days=EXPIRY_WINDOW_DAYS)
    status = request.GET.get('status', 'all')
    q = (request.GET.get('q') or '').strip()
    timed = Q(listing_type__in=['standard', 'urgent'])

    base = Product_Listing.objects.all()
    counts = base.aggregate(
        all=Count('id'),
        suspended=Count('id', filter=Q(is_suspended=True)),
        expiring=Count('id', filter=timed & Q(expiration_date__gt=now, expiration_date__lte=soon)),
        expired=Count('id', filter=timed & Q(expiration_date__lte=now)),
    )

    qs = (base.select_related('seller__user', 'category', 'suspended_by')
          .prefetch_related(Prefetch('images', queryset=Product_Image.objects.only('id', 'product_id', 'image', 'is_primary')))
          .order_by('-created_at'))
    if status == 'suspended':
        qs = qs.filter(is_suspended=True).order_by('-suspended_at')
    elif status == 'expiring':
        qs = qs.filter(timed, expiration_date__gt=now, expiration_date__lte=soon).order_by('expiration_date')
    elif status == 'expired':
        qs = qs.filter(timed, expiration_date__lte=now).order_by('expiration_date')
    else:
        status = 'all'
    if q:
        cond = Q(title__icontains=q) | Q(seller__user__username__icontains=q) | Q(seller__user__email__icontains=q)
        qs = qs.filter(cond)

    page = _paginate(request, qs)
    _attach_cover(page.object_list, now)
    return render(request, 'admin/home_listings.html', {
        'page_obj': page, 'keep': _keep(request), 'status': status, 'q': q, 'counts': counts,
        'next_url': request.get_full_path(),
    })


@staff_required
@require_POST
def listing_suspend(request, pk):
    product = get_object_or_404(Product_Listing, pk=pk)
    reason = _reason(request)
    if not reason:
        messages.error(request, 'A reason is required. The seller receives it by email.')
    elif product.is_suspended:
        messages.info(request, 'That listing is already suspended.')
    else:
        product.suspend(request.user, reason)  # also emails the seller
        messages.success(request, f'"{product.title}" suspended.')
    return redirect(_next(request, 'home_admin_listings'))


@staff_required
@require_POST
def listing_unsuspend(request, pk):
    product = get_object_or_404(Product_Listing, pk=pk)
    if not product.is_suspended:
        messages.info(request, 'That listing is not suspended.')
    else:
        product.unsuspend()  # also emails the seller
        messages.success(request, f'"{product.title}" reinstated.')
    return redirect(_next(request, 'home_admin_listings'))


@staff_required
@require_POST
def listing_delete(request, pk):
    product = get_object_or_404(Product_Listing, pk=pk)
    title = product.title
    logger.info('Staff %s deleted listing %s (%s). Reason: %s',
                request.user.pk, product.pk, title, _reason(request) or 'none given')
    product.delete()
    messages.success(request, f'"{title}" deleted.')
    return redirect(_next(request, 'home_admin_listings'))


# --------------------------------------------------------------------------- reviews
@staff_required
def review_list(request):
    kind = request.GET.get('type', 'all')
    rating = request.GET.get('rating', '')
    q = (request.GET.get('q') or '').strip()

    base = Review.objects.all()
    counts = base.aggregate(
        all=Count('id'),
        product=Count('id', filter=Q(review_type='product')),
        seller=Count('id', filter=Q(review_type='seller')),
        low=Count('id', filter=Q(rating__lte=2)),
    )

    qs = (base.select_related('reviewer', 'product', 'seller__user')
          .prefetch_related(Prefetch('replies', queryset=ReviewReply.objects.select_related('reviewer').order_by('created_at')))
          .order_by('-created_at'))
    if kind in ('product', 'seller'):
        qs = qs.filter(review_type=kind)
    elif kind == 'low':
        qs = qs.filter(rating__lte=2)
    else:
        kind = 'all'
    if rating.isdigit() and 1 <= int(rating) <= 5:
        qs = qs.filter(rating=int(rating))
    else:
        rating = ''
    if q:
        qs = qs.filter(Q(comment__icontains=q) | Q(reviewer__username__icontains=q)
                       | Q(product__title__icontains=q) | Q(seller__user__username__icontains=q))

    return render(request, 'admin/home_reviews.html', {
        'page_obj': _paginate(request, qs), 'keep': _keep(request), 'kind': kind,
        'rating': rating, 'q': q, 'counts': counts, 'stars': [5, 4, 3, 2, 1],
        'next_url': request.get_full_path(),
    })


@staff_required
@require_POST
def review_delete(request, pk):
    review = get_object_or_404(Review, pk=pk)
    logger.info('Staff %s deleted review %s. Reason: %s', request.user.pk, review.pk, _reason(request) or 'none given')
    review.delete()  # replies cascade
    messages.success(request, 'Review deleted.')
    return redirect(_next(request, 'home_admin_reviews'))


@staff_required
@require_POST
def reply_delete(request, pk):
    reply = get_object_or_404(ReviewReply, pk=pk)
    logger.info('Staff %s deleted review reply %s. Reason: %s', request.user.pk, reply.pk, _reason(request) or 'none given')
    reply.delete()
    messages.success(request, 'Reply deleted.')
    return redirect(_next(request, 'home_admin_reviews'))


# --------------------------------------------------------------------------- tools
@staff_required
def tools(request):
    now = timezone.now()
    soon = now + timedelta(days=EXPIRY_WINDOW_DAYS)
    timed = Q(listing_type__in=['standard', 'urgent'])
    stats = Product_Listing.objects.aggregate(
        total=Count('id'),
        expired=Count('id', filter=timed & Q(expiration_date__lte=now)),
        expiring=Count('id', filter=timed & Q(expiration_date__gt=now, expiration_date__lte=soon)),
        warned=Count('id', filter=Q(deletion_warning_sent=True)),
    )
    return render(request, 'admin/home_tools.html', {
        'stats': stats, 'window': EXPIRY_WINDOW_DAYS, 'next_url': request.get_full_path(),
    })


@staff_required
@require_POST
def tool_run(request, action):
    from . import tasks
    back = 'home_admin_tools'
    try:
        if action == 'purge-expired':
            deleted = Product_Listing.delete_expired_listings()
            messages.success(request, f'Deleted {deleted} expired listing(s).')
        elif action == 'boost-scores':
            messages.success(request, tasks.update_all_boost_scores() + '.')
        elif action == 'expiry-warnings':
            now = timezone.now()
            ids = Product_Listing.objects.filter(
                listing_type__in=['standard', 'urgent'],
                expiration_date__gt=now,
                expiration_date__lte=now + timedelta(days=EXPIRY_WINDOW_DAYS),
            ).values_list('id', flat=True)
            sent = 0
            for pid in ids:
                # The task itself only sends when exactly 3 or 1 days remain.
                result = tasks.send_listing_expiry_warning(pid)
                if result and result.startswith('Expiry warning sent'):
                    sent += 1
            messages.success(request, f'Sent {sent} expiry warning(s).')
        else:
            messages.error(request, 'Unknown action.')
    except Exception:
        logger.exception('Home admin tool %s failed', action)
        messages.error(request, 'That job failed. The error is in the server log.')
    return redirect(back)
