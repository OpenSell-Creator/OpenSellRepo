"""
Staff pages for email marketing and communication. These replace the views of the same names in
User/views.py (bulk_email_list, bulk_email_create, bulk_email_detail, bulk_email_send_now,
quick_announcement, email_template_library, email_preference_dashboard, create_missing_preferences,
preview_recipients), with the same url names, so every existing link keeps working.

What changed, and why:
  - Saving a campaign no longer sends it. Create and edit save a draft; sending is a separate,
    confirmed step that shows the recipient count and a preview.
  - One send path: queue with django-q, and fall back to sending inside the request only for a small audience.
  - A send cannot be started twice (a short cache lock plus the draft check).
  - Previews render in a sandboxed frame, so campaign HTML never runs inside the admin page.
  - Recipient counts always come from BulkEmail.get_recipient_count(), the same code the sender uses.
"""
import logging
import re

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.html import linebreaks, strip_tags
from django.views.decorators.http import require_POST

from .email_templates import BY_KEY, TEMPLATES
from .models import BulkEmail, EmailPreferences, Profile
from .utils import bulk_budget_today, bulk_send_plan

logger = logging.getLogger(__name__)

PAGE_SIZE = 20
SYNC_LIMIT = 20             # largest audience sent inside the web request when the queue is down: the sender opens
                            # one SMTP connection per email (about 1 s each), so 20 stays under a 30 s worker timeout
LOCK_SECONDS = 15 * 60
FIX_CAP = 1000
BATCH_TIMEOUT = 600          # per-task django-q timeout; Q_CLUSTER['retry'] must be larger than this
STATUSES = ('all', 'draft', 'active', 'sending', 'partial', 'sent')   # 'active' = sending now + in progress
ACTIVE = ('sending', 'partial')
KNOWN_VARS = ('first_name', 'username', 'site_name', 'site_url')
VAR_RE = re.compile(r'\{\{(\w+)\}\}')          # exactly what the sender replaces: no spaces inside the braces
LOOSE_RE = re.compile(r'\{\{\s*\w+\s*\}\}')
AUDIENCES = [
    ('all', 'Everyone who opted in', 'Every active user who allowed this type of email.'),
    ('verified', 'Verified emails only', 'Only users who confirmed their email address.'),
    ('business', 'Verified businesses only', 'Only users whose business was verified.'),
]

staff_required = user_passes_test(lambda u: u.is_active and u.is_staff)


# --------------------------------------------------------------------------- helpers
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


def sample_html(request, html):
    """Fill the four variables with sample values, for previews only."""
    site = request.build_absolute_uri('/').rstrip('/')
    values = {'first_name': 'Ada', 'username': 'ada_o', 'site_name': 'OpenSell', 'site_url': site}
    return VAR_RE.sub(lambda m: values.get(m.group(1), m.group(0)), html or '')


def unknown_variables(subject, message=''):
    """Tokens the sender will NOT replace, so subscribers would see them as typed."""
    bad = []
    for t in LOOSE_RE.findall(subject or ''):
        if t != '{{first_name}}':
            bad.append(t)       # the sender only fills first_name in the subject
    for t in LOOSE_RE.findall(message or ''):
        if VAR_RE.fullmatch(t) is None or VAR_RE.fullmatch(t).group(1) not in KNOWN_VARS:
            bad.append(t)
    return sorted(set(bad))


def audience_of(c):
    if c.business_only:
        return 'business'
    if c.verified_only:
        return 'verified'
    return 'all'


def audience_label(c):
    return {k: label for k, label, _ in AUDIENCES}[audience_of(c)]


# --------------------------------------------------------------------------- form
class CampaignForm(forms.ModelForm):
    audience = forms.ChoiceField(choices=[(k, l) for k, l, _ in AUDIENCES], initial='all',
                                 widget=forms.RadioSelect)

    class Meta:
        model = BulkEmail
        fields = ['title', 'campaign_type', 'subject', 'message']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'ox-ctl', 'maxlength': 255, 'autocomplete': 'off'}),
            'campaign_type': forms.Select(attrs={'class': 'ox-ctl'}),
            'subject': forms.TextInput(attrs={'class': 'ox-ctl', 'maxlength': 255, 'autocomplete': 'off'}),
            'message': forms.Textarea(attrs={'class': 'ox-ctl ox-code', 'rows': 14, 'spellcheck': 'false'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields['audience'].initial = audience_of(self.instance)

    def clean_title(self):
        t = ' '.join((self.cleaned_data.get('title') or '').split())
        if not t:
            raise forms.ValidationError('Give the campaign a name. Only you see it.')
        return t

    def clean_subject(self):
        s = ' '.join((self.cleaned_data.get('subject') or '').split())
        if not s:
            raise forms.ValidationError('Enter a subject line.')
        return s

    def clean_message(self):
        m = (self.cleaned_data.get('message') or '').strip()
        if len(strip_tags(m).strip()) < 10:
            raise forms.ValidationError('The message is empty or too short to send.')
        return m

    def save(self, commit=True):
        c = super().save(commit=False)
        a = self.cleaned_data['audience']
        c.target_all = True     # the sender never reads this flag, so it is always on
        c.verified_only = a == 'verified'
        c.business_only = a == 'business'
        if commit:
            c.save()
        return c


def _warn_variables(request, campaign):
    bad = unknown_variables(campaign.subject, campaign.message)
    if bad:
        messages.warning(request, 'These will be sent exactly as typed: ' + ', '.join(bad)
                         + '. Use no spaces inside the braces, and only {{first_name}} in the subject. Allowed in the message: '
                         + ', '.join('{{' + v + '}}' for v in KNOWN_VARS) + '.')


# =========================================================================== campaigns
@staff_required
def bulk_email_list(request):
    status = request.GET.get('status', 'all')
    if status not in STATUSES:
        status = 'all'
    q = (request.GET.get('q') or '').strip()
    counts = BulkEmail.objects.aggregate(
        n_all=Count('id'), n_draft=Count('id', filter=Q(status='draft')),
        n_active=Count('id', filter=Q(status__in=ACTIVE)), n_sent=Count('id', filter=Q(status='sent')),
        n_running=Count('id', filter=Q(status='sending')),
    )
    qs = BulkEmail.objects.select_related('created_by')
    if status == 'active':
        qs = qs.filter(status__in=ACTIVE)
    elif status != 'all':
        qs = qs.filter(status=status)
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(subject__icontains=q))
    page = _paginate(request, qs.order_by('-created_at'))
    for c in page.object_list:
        if c.status in ACTIVE:          # x of y for the campaigns that are still going (at most one page of them)
            c.prog = c.progress()
    return render(request, 'admin/bulk_emails.html', {
        'page_obj': page, 'keep': _keep(request), 'status': status, 'q': q, 'counts': counts,
        'any_sending': counts['n_running'] > 0, 'budget': bulk_budget_today(),
        'has_active': counts['n_active'] > 0,
    })


@staff_required
def bulk_email_create(request):
    if request.method == 'POST':
        form = CampaignForm(request.POST)
        if form.is_valid():
            c = form.save(commit=False)
            c.created_by = request.user
            c.status = 'draft'
            c.save()
            messages.success(request, 'Draft saved. Check the preview and the recipient count, then send.')
            _warn_variables(request, c)
            return redirect('bulk_email_detail', pk=c.pk)
        messages.error(request, 'Fix the highlighted fields and save again.')
    else:
        initial = {'audience': 'all'}
        tpl = BY_KEY.get(request.GET.get('template', ''))
        if tpl:
            initial.update(title=tpl['name'], campaign_type=tpl['type'], subject=tpl['subject'], message=tpl['message'])
        form = CampaignForm(initial=initial)
    return render(request, 'admin/bulk_email_create.html', {
        'form': form, 'campaign': None, 'audiences': AUDIENCES, 'variables': KNOWN_VARS,
        'preview_url': reverse('preview_recipients'),
    })


@staff_required
def bulk_email_edit(request, pk):
    c = get_object_or_404(BulkEmail, pk=pk)
    if c.status != 'draft':
        messages.error(request, 'Only drafts can be edited. Duplicate it to reuse the text.')
        return redirect('bulk_email_detail', pk=pk)
    if request.method == 'POST':
        form = CampaignForm(request.POST, instance=c)
        if form.is_valid():
            form.save()
            messages.success(request, 'Draft updated.')
            _warn_variables(request, c)
            return redirect('bulk_email_detail', pk=pk)
        messages.error(request, 'Fix the highlighted fields and save again.')
    else:
        form = CampaignForm(instance=c)
    return render(request, 'admin/bulk_email_create.html', {
        'form': form, 'campaign': c, 'audiences': AUDIENCES, 'variables': KNOWN_VARS,
        'preview_url': reverse('preview_recipients'),
    })


@staff_required
@require_POST
def bulk_email_delete(request, pk):
    c = get_object_or_404(BulkEmail, pk=pk)
    if c.status != 'draft':
        messages.error(request, 'Only drafts can be deleted. Sent campaigns stay as a record.')
        return redirect('bulk_email_detail', pk=pk)
    c.delete()
    messages.success(request, 'Draft deleted.')
    return redirect('bulk_email_list')


@staff_required
@require_POST
def bulk_email_duplicate(request, pk):
    c = get_object_or_404(BulkEmail, pk=pk)
    copy = BulkEmail.objects.create(
        title=('Copy of ' + c.title)[:255], campaign_type=c.campaign_type, subject=c.subject, message=c.message,
        target_all=True, verified_only=c.verified_only, business_only=c.business_only,
        created_by=request.user, status='draft')
    messages.success(request, 'Copied as a new draft.')
    return redirect('bulk_email_edit', pk=copy.pk)


@staff_required
def bulk_email_detail(request, pk):
    c = get_object_or_404(BulkEmail.objects.select_related('created_by'), pk=pk)
    started = c.status != 'draft'
    return render(request, 'admin/bulk_email_detail.html', {
        'campaign': c, 'audience': audience_label(c),
        'prog': c.progress() if started else None,
        'budget': bulk_budget_today() if c.status in ACTIVE else None,
        'failures': list(c.recipient_logs.filter(status='failed').select_related('user').order_by('-updated_at')[:10])
                    if started else [],
        'recipient_count': c.get_recipient_count() if c.status == 'draft' else None,
        'preview_html': sample_html(request, c.message),
        'bad_vars': unknown_variables(c.subject, c.message),
    })


def _lock_key(pk):
    return f'bulk_email_send_{pk}'


@staff_required
def bulk_email_send_now(request, pk):
    c = get_object_or_404(BulkEmail, pk=pk)
    if c.status != 'draft':
        messages.error(request, 'Only drafts can be sent.')
        return redirect('bulk_email_detail', pk=pk)
    count = c.get_recipient_count()
    if count == 0:
        messages.error(request, 'No one matches this audience, so nothing can be sent. Change the audience or the email type.')
        return redirect('bulk_email_detail', pk=pk)

    ctx = {'campaign': c, 'recipient_count': count, 'audience': audience_label(c), 'plan': bulk_send_plan(count),
           'budget': bulk_budget_today(),
           'preview_html': sample_html(request, c.message), 'bad_vars': unknown_variables(c.subject, c.message)}
    if request.method != 'POST':
        return render(request, 'admin/bulk_email_confirm_send.html', ctx)
    if not request.POST.get('confirmed'):
        messages.error(request, 'Tick the box to confirm you checked the preview.')
        return render(request, 'admin/bulk_email_confirm_send.html', ctx)
    if not cache.add(_lock_key(pk), 1, LOCK_SECONDS):
        messages.info(request, 'This campaign was just sent or is being sent. Check its status below.')
        return redirect('bulk_email_detail', pk=pk)

    # draft -> in progress, in one UPDATE: a second click or a second admin cannot start it again
    if not BulkEmail.objects.filter(pk=pk, status='draft').update(status='partial'):
        messages.info(request, 'This campaign was already started. Check its status below.')
        return redirect('bulk_email_detail', pk=pk)

    plan = ctx['plan']
    logger.info('Staff %s started campaign %s (%s recipients)', request.user.pk, c.pk, count)
    try:
        queued = False
        try:
            from django_q.tasks import async_task
            queued = bool(async_task('User.utils.send_bulk_email_batch', c.pk, timeout=BATCH_TIMEOUT, group=f'bulk_email_{c.pk}'))
        except Exception:
            logger.exception('Could not queue campaign %s', c.pk)
        if queued:
            messages.success(request, _plan_text(plan, count, queued=True))
        elif count <= SYNC_LIMIT:
            from .utils import send_bulk_email_batch
            result = send_bulk_email_batch(c.pk, max_emails=SYNC_LIMIT) or {}
            if result.get('success'):
                messages.success(request, f'Sent {result.get("sent", 0)}, failed {result.get("failed", 0)}. ' + _more_text(c.pk))
            else:
                _undo_start(pk)
                messages.error(request, f'Send failed: {result.get("error", "unknown error")}')
        else:
            _undo_start(pk)
            messages.error(request, f'The background queue is not available and {count} people is too many to send during a page load. Start the django-q worker and try again.')
    except Exception:
        _undo_start(pk)
        logger.exception('Campaign %s failed to send', c.pk)
        messages.error(request, 'The send failed. See the server log. Check the status below before trying again.')
    return redirect('bulk_email_detail', pk=pk)


def _undo_start(pk):
    """Back to draft only if nothing was sent, and let the staff member try again at once."""
    c = BulkEmail.objects.filter(pk=pk).first()
    if c and not c.recipient_logs.exists():
        BulkEmail.objects.filter(pk=pk, status__in=ACTIVE).update(status='draft')
        cache.delete(_lock_key(pk))


def _plan_text(plan, count, queued):
    people = f'{count} {"person" if count == 1 else "people"}'
    if plan['today']:
        text = f'Queued. {plan["today"]} go out today'
    else:
        text = 'Queued. Today\'s limit is used up, so sending starts with the next daily batch'
    if plan['days'] > 1:
        text += f' and the rest of the {people} over about {plan["days"]} days ({plan["per_day"]} a day).'
    else:
        text += '.'
    return text


def _more_text(pk):
    c = BulkEmail.objects.get(pk=pk)
    if c.status == 'sent':
        return 'Everyone has been emailed.'
    p = c.progress()
    return f'{p["sent"]} of {p["total"]} done. The rest go out in the next daily batch.'


@staff_required
@require_POST
def bulk_email_send_batch(request):
    """The "Send today's batch" button: same function as the daily schedule."""
    budget = bulk_budget_today()
    active = BulkEmail.objects.filter(status='partial').count()
    if not active:
        messages.info(request, 'No campaign is waiting for a batch.')
    elif budget['left'] <= 0:
        messages.info(request, f'Today\'s limit is used up ({budget["bulk_used"]} of {budget["cap"]}). The next batch runs tomorrow.')
    else:
        queued = False
        try:
            from django_q.tasks import async_task
            queued = bool(async_task('User.utils.send_bulk_email_batch', timeout=BATCH_TIMEOUT, group='bulk_email_batch'))
        except Exception:
            logger.exception('Could not queue the bulk batch')
        if queued:
            messages.success(request, f'Batch queued. Up to {budget["left"]} emails go out now.')
        else:
            from .utils import send_bulk_email_batch      # queue down: never more than SYNC_LIMIT inside a request
            result = send_bulk_email_batch(max_emails=SYNC_LIMIT) or {}
            if result.get('stopped') == 'locked':
                messages.info(request, 'A batch is already running. Check back in a minute.')
            elif result.get('success'):
                messages.warning(request, f'The queue is not available, so up to {SYNC_LIMIT} were sent now: {result.get("sent", 0)} sent, {result.get("failed", 0)} failed.')
            else:
                messages.error(request, f'Send failed: {result.get("error", "unknown error")}')
    back_pk = request.POST.get('pk', '')
    if back_pk.isdigit():
        return redirect('bulk_email_detail', pk=int(back_pk))
    return redirect('bulk_email_list')


@staff_required
@require_POST
def bulk_email_retry_failed(request, pk):
    """Give failed people a fresh set of attempts. They go out in the next batch."""
    with transaction.atomic():
        c = get_object_or_404(BulkEmail.objects.select_for_update(), pk=pk)
        if c.status not in ('partial', 'sent'):
            messages.error(request, 'Nothing to retry for this campaign right now.')
            return redirect('bulk_email_detail', pk=pk)
        n = c.recipient_logs.filter(status='failed').update(attempts=0)
        if n:
            BulkEmail.objects.filter(pk=pk, status='sent').update(status='partial', sent_at=None)
    if n:
        messages.success(request, f'{n} marked for retry. They go out in the next batch. You can also press "Send today\'s batch".')
    else:
        messages.info(request, 'No failed recipients.')
    return redirect('bulk_email_detail', pk=pk)


@staff_required
def quick_announcement(request):
    if request.method == 'POST':
        subject = ' '.join((request.POST.get('subject') or '').split())
        message = (request.POST.get('message') or '').strip()
        audience = request.POST.get('recipient_type', 'all')
        if audience not in ('all', 'verified', 'business'):
            audience = 'all'
        err = ''
        if not subject:
            err = 'Enter a subject.'
        elif len(subject) > 255:
            err = 'The subject is too long. 255 characters at most.'
        elif len(message) < 10:
            err = 'The message is too short to send.'
        if err:
            messages.error(request, err)
            return render(request, 'admin/quick_announcement.html', {
                'subject': subject, 'message': message, 'audience': audience, 'audiences': AUDIENCES})
        c = BulkEmail.objects.create(
            title=f'Quick: {subject[:50]}', campaign_type='announcement', subject=subject,
            message=linebreaks(message, autoescape=True),   # plain text typed here becomes proper paragraphs
            target_all=True, verified_only=audience == 'verified', business_only=audience == 'business',
            created_by=request.user, status='draft')
        return redirect('bulk_email_send_now', pk=c.pk)    # shows the recipient count and asks to confirm
    return render(request, 'admin/quick_announcement.html', {'audience': 'all', 'audiences': AUDIENCES})


@staff_required
def email_template_library(request):
    items = [dict(t, preview=sample_html(request, t['message'])) for t in TEMPLATES]
    return render(request, 'admin/email_template_library.html', {'templates': items, 'variables': KNOWN_VARS})


@staff_required
def preview_recipients(request):
    ctype = request.GET.get('type', '')
    if ctype not in dict(BulkEmail.CAMPAIGN_TYPE_CHOICES):
        return JsonResponse({'count': 0, 'message': 'Choose an email type.'})
    probe = BulkEmail(campaign_type=ctype, verified_only=request.GET.get('verified') == 'true',
                      business_only=request.GET.get('business') == 'true')
    n = probe.get_recipient_count()
    return JsonResponse({'count': n, 'message': f'{n} {"person" if n == 1 else "people"} opted in for {ctype} emails.'})


# =========================================================================== preferences
def _pref_stats():
    prefs = EmailPreferences.objects.aggregate(
        n_prefs=Count('id'),
        n_marketing=Count('id', filter=Q(receive_marketing=True)),
        n_announce=Count('id', filter=Q(receive_announcements=True)),
        n_notify=Count('id', filter=Q(receive_notifications=True)),
        n_none=Count('id', filter=Q(receive_marketing=False, receive_announcements=False, receive_notifications=False)),
    )
    profiles = Profile.objects.count()
    prefs['n_profiles'] = profiles
    prefs['n_missing'] = Profile.objects.filter(email_preferences__isnull=True).count()
    prefs['n_users'] = User.objects.filter(is_active=True).count()
    prefs['n_no_profile'] = User.objects.filter(is_active=True, profile__isnull=True).count()
    return prefs


@staff_required
def email_preference_dashboard(request):
    s = _pref_stats()
    base = s['n_prefs'] or 1
    rows = [
        {'label': 'Marketing and newsletters', 'n': s['n_marketing'], 'pct': round(s['n_marketing'] * 100 / base)},
        {'label': 'Announcements', 'n': s['n_announce'], 'pct': round(s['n_announce'] * 100 / base)},
        {'label': 'Notifications', 'n': s['n_notify'], 'pct': round(s['n_notify'] * 100 / base)},
    ]
    return render(request, 'admin/email_preference_dashboard.html', {'stats': s, 'rows': rows})


@staff_required
def create_missing_preferences(request):
    if request.method == 'POST':
        made = 0
        for p in Profile.objects.filter(email_preferences__isnull=True)[:FIX_CAP]:
            try:
                EmailPreferences.objects.create(profile=p)   # save() also makes their unsubscribe token
                made += 1
            except Exception:
                logger.warning('Could not create email preferences for profile %s', p.pk, exc_info=True)
        left = Profile.objects.filter(email_preferences__isnull=True).count()
        if made:
            messages.success(request, f'Created preferences for {made} {"person" if made == 1 else "people"}. They are opted in, like new sign-ups.')
        else:
            messages.info(request, 'Everyone already has email preferences.')
        if left:
            messages.warning(request, f'{left} still have none. Run it again.')
        return redirect('email_preference_dashboard')
    return render(request, 'admin/create_missing_preferences.html', {'missing_count': _pref_stats()['n_missing']})
