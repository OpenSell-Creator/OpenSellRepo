"""
Staff pages for the User app: a people directory, one page per person, states and LGAs,
and an overview with a repair tool.

Rules that hold on every page:
  - staff-only, every change is a POST
  - nobody can act on a superuser or on themselves
  - only a superuser can act on another staff member, or grant or remove staff status
  - accounts are never deleted here. Deleting a user cascades into wallet and transaction records,
    so the way to remove someone is to deactivate them, which keeps the history.
"""
import logging
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Count, Q
from django.db.models.functions import TruncWeek
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .models import ItemReport, LGA, Location, Profile, State

logger = logging.getLogger(__name__)

PAGE_SIZE = 20
NEW_DAYS = 7
OPEN_REPORT = ('pending', 'reviewing')
REPAIR_CAP = 500
PRIVILEGES = {
    'featured_store': 'Featured store',
    'priority_support': 'Priority support',
    'permanent_listing_enabled': 'Permanent listings',
}
FILTERS = ('all', 'staff', 'inactive', 'unverified', 'business', 'pending', 'new', 'noprofile')

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


def _blocked(actor, target):
    """Why `actor` may not change `target`, or '' when they may."""
    if target.pk == actor.pk:
        return 'You cannot do that to your own account.'
    if target.is_superuser:
        return 'Superuser accounts cannot be changed here.'
    if target.is_staff and not actor.is_superuser:
        return 'Only a superuser can change a staff account.'
    return ''


def _photo_url(profile):
    try:
        return profile.photo.url if profile and profile.photo else ''
    except Exception:
        return ''


def users_admin_stats():
    """Counts for the panel links. Merge into the admin_panel context."""
    row = User.objects.aggregate(
        n_all=Count('id'),
        n_inactive=Count('id', filter=Q(is_active=False)),
        n_noprofile=Count('id', filter=Q(profile__isnull=True)),
    )
    return {'users_total': row['n_all'], 'users_inactive': row['n_inactive'],
            'users_no_profile': row['n_noprofile']}


# =========================================================================== people
@staff_required
def user_list(request):
    now = timezone.now()
    flt = request.GET.get('status', 'all')
    if flt not in FILTERS:
        flt = 'all'
    q = (request.GET.get('q') or '').strip()

    counts = User.objects.aggregate(
        n_all=Count('id'),
        n_staff=Count('id', filter=Q(is_staff=True)),
        n_inactive=Count('id', filter=Q(is_active=False)),
        n_new=Count('id', filter=Q(date_joined__gte=now - timedelta(days=NEW_DAYS))),
        n_noprofile=Count('id', filter=Q(profile__isnull=True)),
    )
    prof = Profile.objects.aggregate(
        n_unverified=Count('id', filter=Q(email_verified=False)),
        n_business=Count('id', filter=Q(business_verification_status='verified')),
        n_pending=Count('id', filter=Q(business_verification_status='pending')),
    )
    counts.update(prof)

    qs = User.objects.select_related('profile').order_by('-date_joined')
    if flt == 'staff':
        qs = qs.filter(is_staff=True)
    elif flt == 'inactive':
        qs = qs.filter(is_active=False)
    elif flt == 'unverified':
        qs = qs.filter(profile__email_verified=False)
    elif flt == 'business':
        qs = qs.filter(profile__business_verification_status='verified')
    elif flt == 'pending':
        qs = qs.filter(profile__business_verification_status='pending')
    elif flt == 'new':
        qs = qs.filter(date_joined__gte=now - timedelta(days=NEW_DAYS))
    elif flt == 'noprofile':
        qs = qs.filter(profile__isnull=True)
    if q:
        qs = qs.filter(Q(username__icontains=q) | Q(email__icontains=q) | Q(first_name__icontains=q)
                       | Q(last_name__icontains=q) | Q(profile__phone_number__icontains=q)
                       | Q(profile__business_name__icontains=q))

    page = _paginate(request, qs)
    for u in page.object_list:
        p = getattr(u, 'profile', None)
        u.prof = p
        u.photo_url = _photo_url(p)
        u.locked = _blocked(request.user, u)
    return render(request, 'admin/usr_list.html', {
        'page_obj': page, 'keep': _keep(request), 'status': flt, 'q': q, 'counts': counts,
        'next_url': request.get_full_path(),
    })


def _activity(profile):
    """Live listing counts. Each app is optional so one missing app cannot break the page."""
    out = {'products': None, 'services': None, 'requests': None}
    open_reports = 0
    for key, mod, cls, field in (('products', 'Home.models', 'Product_Listing', 'seller'),
                                 ('services', 'Services.models', 'ServiceListing', 'provider'),
                                 ('requests', 'BuyerRequest.models', 'BuyerRequest', 'buyer')):
        try:
            module = __import__(mod, fromlist=[cls])
            model = getattr(module, cls)
            rows = model.objects.filter(**{field: profile})
            out[key] = rows.count()
            if key != 'requests':
                ids = [str(i) for i in rows.values_list('pk', flat=True)[:500]]
                if ids:
                    open_reports += ItemReport.objects.filter(
                        content_type=ContentType.objects.get_for_model(model),
                        object_id__in=ids, status__in=OPEN_REPORT).count()
        except Exception:
            out[key] = None
    return out, open_reports


@staff_required
def user_detail(request, pk):
    u = get_object_or_404(User.objects.select_related('profile', 'profile__location__state', 'profile__location__lga'), pk=pk)
    p = getattr(u, 'profile', None)
    activity, open_reports = _activity(p) if p else ({'products': None, 'services': None, 'requests': None}, 0)
    filed = ItemReport.objects.filter(reporter_email__iexact=u.email).count() if u.email else 0
    return render(request, 'admin/usr_detail.html', {
        'u': u, 'p': p, 'photo_url': _photo_url(p), 'activity': activity, 'open_reports': open_reports,
        'filed_reports': filed, 'locked': _blocked(request.user, u),
        'privileges': [(k, v, bool(p and getattr(p, k))) for k, v in PRIVILEGES.items()] if p else [],
        'next_url': request.get_full_path(),
    })


def _guard(request, target):
    why = _blocked(request.user, target)
    if why:
        messages.error(request, why)
    return why


@staff_required
@require_POST
def user_deactivate(request, pk):
    u = get_object_or_404(User, pk=pk)
    reason = _reason(request)
    if _guard(request, u):
        pass
    elif not reason:
        messages.error(request, 'A reason is required. It is kept in the server log.')
    elif not u.is_active:
        messages.info(request, 'That account is already deactivated.')
    else:
        User.objects.filter(pk=u.pk).update(is_active=False)
        logger.info('Staff %s deactivated user %s (%s). Reason: %s', request.user.pk, u.pk, u.username, reason)
        messages.success(request, f'@{u.username} deactivated. They are signed out and cannot log in. Their listings stay up until you suspend them.')
    return redirect(_next(request, 'usr_admin_detail', pk))


@staff_required
@require_POST
def user_reactivate(request, pk):
    u = get_object_or_404(User, pk=pk)
    if _guard(request, u):
        pass
    elif u.is_active:
        messages.info(request, 'That account is already active.')
    else:
        User.objects.filter(pk=u.pk).update(is_active=True)
        logger.info('Staff %s reactivated user %s (%s)', request.user.pk, u.pk, u.username)
        messages.success(request, f'@{u.username} can log in again.')
    return redirect(_next(request, 'usr_admin_detail', pk))


@staff_required
@require_POST
def user_staff(request, pk):
    u = get_object_or_404(User, pk=pk)
    on = request.POST.get('to') == 'on'
    if not request.user.is_superuser:
        messages.error(request, 'Only a superuser can change staff access.')
    elif _guard(request, u):
        pass
    elif on and not u.is_active:
        messages.error(request, 'Reactivate the account before making it staff.')
    else:
        User.objects.filter(pk=u.pk).update(is_staff=on)
        logger.info('Superuser %s set is_staff=%s on user %s (%s)', request.user.pk, on, u.pk, u.username)
        messages.success(request, f'@{u.username} is {"now" if on else "no longer"} staff.')
    return redirect(_next(request, 'usr_admin_detail', pk))


@staff_required
@require_POST
def user_verify_email(request, pk):
    u = get_object_or_404(User.objects.select_related('profile'), pk=pk)
    p = getattr(u, 'profile', None)
    if _guard(request, u):
        pass
    elif not p:
        messages.error(request, 'This account has no profile yet. Create it from the overview page first.')
    elif p.email_verified:
        messages.info(request, 'That email is already verified.')
    else:
        Profile.objects.filter(pk=p.pk).update(email_verified=True, email_otp=None, otp_created_at=None)
        logger.info('Staff %s verified email of user %s', request.user.pk, u.pk)
        messages.success(request, 'Email marked as verified.')
    return redirect(_next(request, 'usr_admin_detail', pk))


@staff_required
@require_POST
def user_clear_profile(request, pk, what):
    u = get_object_or_404(User.objects.select_related('profile'), pk=pk)
    p = getattr(u, 'profile', None)
    if _guard(request, u):
        pass
    elif not p or what not in ('photo', 'bio'):
        messages.error(request, 'Nothing to clear.')
    elif what == 'photo':
        if not p.photo:
            messages.info(request, 'They have no photo.')
        else:
            try:
                p.photo.delete(save=False)       # remove the file
            except Exception:
                logger.warning('Could not delete photo file for profile %s', p.pk, exc_info=True)
            Profile.objects.filter(pk=p.pk).update(photo=None)   # update() skips Profile.save()
            logger.info('Staff %s removed photo of user %s. Reason: %s', request.user.pk, u.pk, _reason(request) or 'none given')
            messages.success(request, 'Photo removed.')
    else:
        if not p.bio:
            messages.info(request, 'Their bio is already empty.')
        else:
            Profile.objects.filter(pk=p.pk).update(bio='')
            logger.info('Staff %s cleared bio of user %s. Reason: %s', request.user.pk, u.pk, _reason(request) or 'none given')
            messages.success(request, 'Bio cleared.')
    return redirect(_next(request, 'usr_admin_detail', pk))


@staff_required
@require_POST
def user_privilege(request, pk, field):
    u = get_object_or_404(User.objects.select_related('profile'), pk=pk)
    p = getattr(u, 'profile', None)
    on = request.POST.get('to') == 'on'
    if field not in PRIVILEGES:
        messages.error(request, 'Unknown setting.')
    elif _guard(request, u):
        pass
    elif not p:
        messages.error(request, 'This account has no profile yet.')
    else:
        Profile.objects.filter(pk=p.pk).update(**{field: on})
        logger.info('Staff %s set %s=%s on user %s', request.user.pk, field, on, u.pk)
        messages.success(request, f'{PRIVILEGES[field]} turned {"on" if on else "off"} for @{u.username}.')
    return redirect(_next(request, 'usr_admin_detail', pk))


# =========================================================================== locations
def _clean_name(raw):
    name = ' '.join((raw or '').split())
    if len(name) < 2:
        return '', 'Enter a name of at least 2 characters.'
    if len(name) > 100:
        return '', 'That name is too long. 100 characters at most.'
    return name, ''


@staff_required
def location_list(request):
    q = (request.GET.get('q') or '').strip()
    states = State.objects.annotate(n_lgas=Count('lgas', distinct=True),
                                    n_people=Count('location__profile', distinct=True))
    if q:
        states = states.filter(name__icontains=q)
    totals = State.objects.aggregate(n_states=Count('id'), n_off=Count('id', filter=Q(is_active=False)))
    totals['n_lgas'] = LGA.objects.count()
    totals['n_lgas_off'] = LGA.objects.filter(is_active=False).count()
    return render(request, 'admin/usr_locations.html', {
        'states': states.order_by('name'), 'q': q, 'totals': totals, 'next_url': request.get_full_path(),
    })


@staff_required
@require_POST
def state_add(request):
    name, err = _clean_name(request.POST.get('name'))
    if err:
        messages.error(request, err)
    elif State.objects.filter(name__iexact=name).exists():
        messages.error(request, f'"{name}" already exists.')
    else:
        s = State.objects.create(name=name)
        messages.success(request, f'Added {s.name}. Add its LGAs next.')
        return redirect('usr_admin_state', s.pk)
    return redirect('usr_admin_locations')


@staff_required
def state_detail(request, pk):
    state = get_object_or_404(State, pk=pk)
    q = (request.GET.get('q') or '').strip()
    lgas = state.lgas.annotate(n_people=Count('location__profile', distinct=True))
    if q:
        lgas = lgas.filter(name__icontains=q)
    people = Profile.objects.filter(location__state=state).count()
    page = _paginate(request, lgas.order_by('name'), size=40)
    return render(request, 'admin/usr_state.html', {
        'state': state, 'page_obj': page, 'keep': _keep(request), 'q': q, 'people': people,
        'n_lgas': state.lgas.count(), 'next_url': request.get_full_path(),
    })


@staff_required
@require_POST
def state_update(request, pk):
    state = get_object_or_404(State, pk=pk)
    action = request.POST.get('action')
    if action == 'rename':
        name, err = _clean_name(request.POST.get('name'))
        if err:
            messages.error(request, err)
        elif State.objects.filter(name__iexact=name).exclude(pk=state.pk).exists():
            messages.error(request, f'"{name}" already exists.')
        else:
            State.objects.filter(pk=state.pk).update(name=name)
            messages.success(request, 'Renamed.')
    elif action in ('on', 'off'):
        State.objects.filter(pk=state.pk).update(is_active=(action == 'on'))
        messages.success(request, f'{state.name} is {"shown in" if action == "on" else "hidden from"} the location pickers.')
    elif action == 'delete':
        if Location.objects.filter(state=state).exists():
            messages.error(request, f'{state.name} is used by saved addresses. Hide it instead of deleting it.')
        else:
            name = state.name
            state.delete()    # its empty LGAs go with it
            messages.success(request, f'Deleted {name}.')
            return redirect('usr_admin_locations')
    else:
        messages.error(request, 'Unknown action.')
    return redirect(_next(request, 'usr_admin_state', pk))


@staff_required
@require_POST
def lga_add(request, pk):
    state = get_object_or_404(State, pk=pk)
    name, err = _clean_name(request.POST.get('name'))
    if err:
        messages.error(request, err)
    elif LGA.objects.filter(state=state, name__iexact=name).exists():
        messages.error(request, f'{name} already exists in {state.name}.')
    else:
        LGA.objects.create(state=state, name=name)
        messages.success(request, f'Added {name}.')
    return redirect('usr_admin_state', pk)


@staff_required
@require_POST
def lga_update(request, pk):
    lga = get_object_or_404(LGA, pk=pk)
    action = request.POST.get('action')
    if action in ('on', 'off'):
        LGA.objects.filter(pk=lga.pk).update(is_active=(action == 'on'))
        messages.success(request, f'{lga.name} {"shown" if action == "on" else "hidden"}.')
    elif action == 'delete':
        if Location.objects.filter(lga=lga).exists():
            messages.error(request, f'{lga.name} is used by saved addresses. Hide it instead of deleting it.')
        else:
            lga.delete()
            messages.success(request, 'Deleted.')
    else:
        messages.error(request, 'Unknown action.')
    return redirect(_next(request, 'usr_admin_state', lga.state_id))


# =========================================================================== overview
@staff_required
def overview(request):
    now = timezone.now()
    day, week, month = now - timedelta(days=1), now - timedelta(days=7), now - timedelta(days=30)
    u = User.objects.aggregate(
        n_all=Count('id'), n_day=Count('id', filter=Q(date_joined__gte=day)),
        n_week=Count('id', filter=Q(date_joined__gte=week)), n_month=Count('id', filter=Q(date_joined__gte=month)),
        n_active30=Count('id', filter=Q(last_login__gte=month)),
        n_staff=Count('id', filter=Q(is_staff=True)), n_inactive=Count('id', filter=Q(is_active=False)),
        n_noprofile=Count('id', filter=Q(profile__isnull=True)),
    )
    p = Profile.objects.aggregate(
        n_profiles=Count('id'), n_verified_email=Count('id', filter=Q(email_verified=True)),
        n_photo=Count('id', filter=~Q(photo='') & Q(photo__isnull=False)),
    )
    biz_rows = Profile.objects.values('business_verification_status').annotate(n=Count('id'))
    biz_map = {r['business_verification_status']: r['n'] for r in biz_rows}
    labels = dict(Profile._meta.get_field('business_verification_status').choices)
    biz_top = max(biz_map.values() or [1])
    business = [{'label': lab, 'n': biz_map.get(key, 0), 'pct': round(biz_map.get(key, 0) * 100 / biz_top) if biz_top else 0}
                for key, lab in labels.items()]

    weeks = list(User.objects.filter(date_joined__gte=now - timedelta(weeks=8))
                 .annotate(w=TruncWeek('date_joined')).values('w').annotate(n=Count('id')).order_by('w'))
    wk_top = max([r['n'] for r in weeks] or [1])
    signups = [{'label': r['w'].strftime('%b %d'), 'n': r['n'], 'pct': round(r['n'] * 100 / wk_top)} for r in weeks]
    verified_pct = round(p['n_verified_email'] * 100 / p['n_profiles']) if p['n_profiles'] else 0
    return render(request, 'admin/usr_overview.html', {
        'u': u, 'p': p, 'business': business, 'signups': signups, 'verified_pct': verified_pct,
        'next_url': request.get_full_path(),
    })


@staff_required
@require_POST
def tool_run(request, action):
    back = _next(request, 'usr_admin_overview')
    if action == 'profiles':
        made = 0
        for user in User.objects.filter(profile__isnull=True)[:REPAIR_CAP]:
            try:
                Profile.objects.create(user=user)     # Profile.save() also creates their email preferences
                made += 1
            except Exception:
                logger.warning('Could not create a profile for user %s', user.pk, exc_info=True)
        left = User.objects.filter(profile__isnull=True).count()
        if made:
            messages.success(request, f'Created {made} missing profile{"s" if made != 1 else ""}.')
        else:
            messages.info(request, 'Every account already has a profile.')
        if left:
            messages.warning(request, f'{left} still have none. Run it again, or check the server log.')
    else:
        messages.error(request, 'Unknown tool.')
    return redirect(back)
