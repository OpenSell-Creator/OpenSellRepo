import datetime
import smtplib
from unittest import mock

from django.contrib.auth.models import User
from django.core import mail
from django.core.cache import cache
from django.core.mail.backends import locmem
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from User import utils
from User.email_backend import CountingMixin
from User.models import BulkEmail, BulkEmailRecipient, EmailSendCounter


class CountingLocmem(CountingMixin, locmem.EmailBackend):
    pass


UTC = datetime.timezone.utc
DAY1 = datetime.datetime(2026, 11, 10, 9, 0, tzinfo=UTC)


class Clock:
    def __init__(self, dt):
        self.dt = dt

    def now(self):
        return self.dt

    def go(self, **kw):
        self.dt += datetime.timedelta(**kw)


@override_settings(EMAIL_BACKEND='User.tests_bulk_email.CountingLocmem', BULK_EMAIL_DAILY_CAP=75, EMAIL_DAILY_LIMIT=100)
class BatchBase(TestCase):
    N = 250

    @classmethod
    def make_users(cls, n):
        for i in range(n):
            User.objects.create_user(f'u{i}', f'u{i}@example.com', 'pw', first_name=f'N{i}')

    def setUp(self):
        cache.clear()
        self.clock = Clock(DAY1)
        p = mock.patch('django.utils.timezone.now', self.clock.now)
        p.start()
        self.addCleanup(p.stop)
        self.staff = User.objects.create_user('boss', 'boss@example.com', 'pw', is_staff=True)
        self.make_users(self.N)
        mail.outbox = []

    def campaign(self, **kw):
        d = dict(title='T', campaign_type='announcement', subject='Hi {{first_name}}',
                 message='<p>Hello {{first_name}} ({{username}}) at {{site_name}} {{site_url}}</p>',
                 created_by=self.staff, status='partial')
        d.update(kw)
        return BulkEmail.objects.create(**d)

    def recipients_emailed(self):
        out = [a for m in mail.outbox for a in m.to]
        return out


class DailyCapTests(BatchBase):
    def test_four_days_no_duplicates(self):
        c = self.campaign()
        total = c.get_recipient_count()
        self.assertEqual(total, self.N + 1)    # boss is a user too
        r = utils.send_bulk_email_batch(c.pk)
        self.assertEqual((r['sent'], r['stopped']), (75, 'budget'))
        c.refresh_from_db()
        self.assertEqual((c.status, c.total_sent, c.sent_at), ('partial', 75, None))
        self.assertEqual(c.progress()['sent'], 75)
        # second run the same day does nothing
        r = utils.send_bulk_email_batch(c.pk)
        self.assertEqual(r['sent'], 0)
        self.assertEqual(len(mail.outbox), 75)
        for day in (2, 3):
            self.clock.go(days=1)
            self.assertEqual(utils.send_bulk_email_batch()['sent'], 75)
            self.assertEqual(BulkEmail.objects.get(pk=c.pk).status, 'partial')
        self.clock.go(days=1)
        r = utils.send_bulk_email_batch()
        self.assertEqual(r['sent'], total - 225)
        c.refresh_from_db()
        self.assertEqual((c.status, c.total_sent), ('sent', total))
        self.assertIsNotNone(c.sent_at)
        got = self.recipients_emailed()
        self.assertEqual(len(got), total)
        self.assertEqual(len(set(got)), total)           # nobody twice
        self.assertEqual(BulkEmailRecipient.objects.filter(status='sent').count(), total)
        self.assertEqual(utils.send_bulk_email_batch()['sent'], 0)   # finished stays finished
        self.assertEqual(len(mail.outbox), total)

    def test_cap_is_shared_by_all_campaigns(self):
        a = self.campaign(title='A')
        self.clock.go(minutes=1)
        b = self.campaign(title='B')
        utils.send_bulk_email_batch()
        self.assertEqual(BulkEmailRecipient.objects.filter(status='sent').count(), 75)
        self.assertEqual(a.recipient_logs.count(), 75)
        self.assertEqual(b.recipient_logs.count(), 0)     # oldest first
        self.assertEqual(BulkEmail.objects.get(pk=b.pk).status, 'partial')

    def test_other_emails_shrink_the_budget(self):
        self.campaign()
        for i in range(40):                                # OTP / welcome emails sent through the counting backend
            mail.send_mail('otp', 'x', 'a@b.c', [f'o{i}@example.com'])
        self.assertEqual(EmailSendCounter.objects.get().total, 40)
        b = utils.bulk_budget_today()
        self.assertEqual((b['other_used'], b['left']), (40, 60))      # 100 - 40
        self.assertEqual(utils.send_bulk_email_batch()['sent'], 60)
        # 100 emails today, and the transactional ones can still use nothing more only if they exceed the plan:
        self.assertEqual(EmailSendCounter.objects.get().total, 100)
        self.assertEqual(utils.bulk_budget_today()['left'], 0)

    def test_small_transactional_use_keeps_full_cap(self):
        self.campaign()
        for i in range(10):
            mail.send_mail('otp', 'x', 'a@b.c', [f'o{i}@example.com'])
        self.assertEqual(utils.bulk_budget_today()['left'], 75)       # inside the 25 reserve
        self.assertEqual(utils.send_bulk_email_batch()['sent'], 75)
        self.assertEqual(utils.bulk_budget_today()['other_used'], 10)

    def test_without_counter_it_is_the_plain_cap(self):
        self.assertEqual(utils.bulk_budget_today()['left'], 75)
        with override_settings(BULK_EMAIL_DAILY_CAP=10):
            self.assertEqual(utils.bulk_budget_today()['left'], 10)

    def test_max_emails_limit(self):
        c = self.campaign()
        self.assertEqual(utils.send_bulk_email_batch(c.pk, max_emails=20)['sent'], 20)

    def test_day_boundary_is_utc_midnight(self):
        self.campaign()
        self.clock.dt = datetime.datetime(2026, 11, 10, 23, 50, tzinfo=UTC)
        utils.send_bulk_email_batch()
        self.assertEqual(utils.bulk_budget_today()['left'], 0)
        self.clock.dt = datetime.datetime(2026, 11, 11, 0, 5, tzinfo=UTC)
        self.assertEqual(utils.bulk_budget_today()['left'], 75)


class FailureTests(BatchBase):
    N = 12

    def failing_for(self, *emails, exc=None):
        real = utils.EmailMultiAlternatives if hasattr(utils, 'EmailMultiAlternatives') else None
        from django.core.mail import EmailMultiAlternatives
        orig = EmailMultiAlternatives.send

        def send(self_, fail_silently=False):
            if any(t in emails for t in self_.to):
                raise exc or smtplib.SMTPRecipientsRefused({})
            return orig(self_, fail_silently)
        p = mock.patch.object(EmailMultiAlternatives, 'send', send)
        p.start()
        self.addCleanup(p.stop)
        return p

    def test_failed_is_logged_and_retried_next_day(self):
        c = self.campaign()
        p = self.failing_for('u3@example.com')
        r = utils.send_bulk_email_batch(c.pk)
        self.assertEqual((r['sent'], r['failed']), (12, 1))   # 13 users incl. boss
        log = c.recipient_logs.get(user__username='u3')
        self.assertEqual((log.status, log.attempts), ('failed', 1))
        self.assertTrue(log.error)
        self.assertEqual(BulkEmail.objects.get(pk=c.pk).status, 'partial')   # not 'sent' while someone can still be tried
        p.stop()
        self.clock.go(days=1)
        r = utils.send_bulk_email_batch(c.pk)
        self.assertEqual((r['sent'], r['failed']), (1, 0))
        self.assertEqual(BulkEmail.objects.get(pk=c.pk).status, 'sent')
        self.assertEqual(len(set(self.recipients_emailed())), 13)
        self.assertEqual(len(mail.outbox), 13)

    def test_attempts_run_out_then_staff_retry(self):
        c = self.campaign()
        self.failing_for('u3@example.com')
        for _ in range(3):
            utils.send_bulk_email_batch(c.pk)
            self.clock.go(days=1)
        log = c.recipient_logs.get(user__username='u3')
        self.assertEqual((log.status, log.attempts), ('failed', 3))
        c.refresh_from_db()
        self.assertEqual((c.status, c.total_sent), ('sent', 12))     # nobody left to try
        self.assertEqual(c.progress()['failed'], 1)
        self.assertEqual(c.progress()['sent'], 12)
        utils.send_bulk_email_batch(c.pk)                           # does not touch a finished campaign
        self.assertEqual(log.__class__.objects.get(pk=log.pk).attempts, 3)
        # staff retry
        self.client.force_login(self.staff)
        r = self.client.post(reverse('bulk_email_retry_failed', args=[c.pk]))
        self.assertEqual(r.status_code, 302)
        c.refresh_from_db()
        self.assertEqual((c.status, c.sent_at), ('partial', None))
        mock.patch.stopall()
        self.setUp_clock_again()
        r = utils.send_bulk_email_batch(c.pk)
        self.assertEqual(r['sent'], 1)
        self.assertEqual(BulkEmail.objects.get(pk=c.pk).status, 'sent')
        self.assertEqual(len(set(self.recipients_emailed())), 13)

    def setUp_clock_again(self):
        p = mock.patch('django.utils.timezone.now', self.clock.now)
        p.start()
        self.addCleanup(p.stop)

    def test_circuit_breaker_gives_attempts_back(self):
        c = self.campaign()
        self.failing_for(*[u.email for u in User.objects.all()], exc=smtplib.SMTPServerDisconnected('down'))
        r = utils.send_bulk_email_batch(c.pk)
        self.assertEqual((r['sent'], r['failed'], r['stopped']), (0, 3, 'provider'))
        self.assertEqual(list(c.recipient_logs.values_list('attempts', flat=True)), [0, 0, 0])
        self.assertEqual(BulkEmail.objects.get(pk=c.pk).status, 'partial')

    def test_crash_mid_batch_never_duplicates(self):
        c = self.campaign()
        orig = utils.send_single_email
        calls = {'n': 0}

        def boom(user, campaign):
            calls['n'] += 1
            if calls['n'] == 6:
                raise SystemExit('worker killed')       # not an Exception: nothing in the loop catches it
            return orig(user, campaign)
        with mock.patch.object(utils, 'send_single_email', boom):
            with self.assertRaises(SystemExit):
                utils.send_bulk_email_batch(c.pk)
        self.assertEqual(len(mail.outbox), 5)
        c.refresh_from_db()
        self.assertEqual(c.status, 'partial')                         # not back to draft
        self.assertIsNone(cache.get(utils.BULK_LOCK_KEY))             # lock released
        self.assertEqual(c.recipient_logs.filter(status='sending').count(), 1)
        r = utils.send_bulk_email_batch(c.pk)                         # re-run: the other 7 only
        self.assertEqual(r['sent'], 7)
        self.assertEqual(len(mail.outbox), 12)
        self.assertEqual(len(set(self.recipients_emailed())), 12)
        c.refresh_from_db()
        self.assertEqual(c.status, 'partial')                         # the claimed one is unknown, so not finished
        self.clock.go(hours=3)
        utils.send_bulk_email_batch(c.pk)                             # stale claim released as failed, no resend
        self.assertEqual(len(mail.outbox), 12)
        c.refresh_from_db()
        self.assertEqual(c.status, 'sent')
        stuck = c.recipient_logs.get(status='failed')
        self.assertIn('delivery unknown', stuck.error)

    def test_claim_is_exclusive(self):
        c = self.campaign()
        uid = User.objects.first().pk
        self.assertIsNotNone(utils._claim(c, uid))
        self.assertIsNone(utils._claim(c, uid))
        self.assertEqual(c.recipient_logs.count(), 1)

    def test_batch_lock(self):
        c = self.campaign()
        cache.add(utils.BULK_LOCK_KEY, 1, 60)
        r = utils.send_bulk_email_batch(c.pk)
        self.assertEqual((r['sent'], r['stopped']), (0, 'locked'))
        self.assertEqual(len(mail.outbox), 0)

    def test_unexpected_error_returns_failure_and_releases_lock(self):
        with mock.patch.object(utils, '_release_stale_claims', side_effect=RuntimeError('db')):
            r = utils.send_bulk_email_batch()
        self.assertFalse(r['success'])
        self.assertIsNone(cache.get(utils.BULK_LOCK_KEY))


class RecipientAndTemplateTests(BatchBase):
    N = 4

    def test_excluded_recipients(self):
        User.objects.filter(username='u0').update(email='')
        u1 = User.objects.get(username='u1')
        u1.profile.email_preferences.__class__.objects.filter(profile=u1.profile).update(receive_announcements=False)
        User.objects.filter(username='u2').update(is_active=False)
        c = self.campaign()
        names = set(c.get_recipients_query().values_list('username', flat=True))
        self.assertEqual(names, {'u3', 'boss'})

    def test_variables(self):
        u = User.objects.get(username='u0')
        u.first_name = '<b>Ada</b> {{username}}'
        u.save()
        c = self.campaign(subject='Hi {{first_name}} {{username}} {{ first_name }}',
                          message='<p>{{first_name}}|{{username}}|{{site_name}}|{{site_url}}|{{ first_name }}|{{nope}}</p>')
        utils.send_single_email(u, c)
        m = mail.outbox[0]
        self.assertEqual(m.subject, 'Hi <b>Ada</b> {{username}} {{username}} {{ first_name }}')
        html_body = m.alternatives[0][0]
        self.assertIn('&lt;b&gt;Ada&lt;/b&gt; {{username}}|u0|OpenSell|https://opensell.ng|{{ first_name }}|{{nope}}', html_body)
        self.assertNotIn('<b>Ada</b>', html_body)
        self.assertIn('Ada {{username}}|u0|OpenSell|https://opensell.ng|{{ first_name }}|{{nope}}', m.body)   # plain text: tags stripped

    def test_subject_has_no_newline(self):
        u = User.objects.get(username='u0')
        u.first_name = 'Ada\nBcc: x@y.z'
        u.save()
        utils.send_single_email(u, self.campaign(subject='Hi {{first_name}}'))
        self.assertNotIn('\n', mail.outbox[0].subject)

    def test_single_send_raises_without_preferences(self):
        u = User.objects.get(username='u0')
        u.profile.email_preferences.delete()
        u = User.objects.get(username='u0')
        with self.assertRaises(ValueError):
            utils.send_single_email(u, self.campaign())


class ViewTests(BatchBase):
    N = 100

    def setUp(self):
        super().setUp()
        self.client.force_login(self.staff)

    def draft(self, **kw):
        return self.campaign(status='draft', **kw)

    def test_confirm_start_and_progress_pages(self):
        c = self.draft()
        r = self.client.get(reverse('bulk_email_send_now', args=[c.pk]))
        self.assertContains(r, 'Start: send 75 today')
        self.assertContains(r, 'about 2 days')
        r = self.client.post(reverse('bulk_email_send_now', args=[c.pk]), {'confirmed': '1'}, follow=True)
        self.assertContains(r, '75 go out today')
        c.refresh_from_db()
        self.assertEqual(c.status, 'partial')
        self.assertEqual(len(mail.outbox), 75)
        self.assertContains(r, '75 of 101 sent')
        lst = self.client.get(reverse('bulk_email_list'))
        self.assertContains(lst, '75 of 101 sent')
        self.assertContains(lst, 'Send today')
        self.assertContains(lst, 'In progress')
        # second start attempt is refused
        r = self.client.post(reverse('bulk_email_send_now', args=[c.pk]), {'confirmed': '1'}, follow=True)
        self.assertEqual(len(mail.outbox), 75)
        # manual batch button: limit already used
        r = self.client.post(reverse('bulk_email_send_batch'), {'pk': c.pk}, follow=True)
        self.assertContains(r, 'limit is used up')
        self.clock.go(days=1)
        r = self.client.post(reverse('bulk_email_send_batch'), {'pk': c.pk}, follow=True)
        self.assertEqual(len(mail.outbox), 101)
        c.refresh_from_db()
        self.assertEqual(c.status, 'sent')
        self.assertContains(self.client.get(reverse('bulk_email_detail', args=[c.pk])), '101 of 101')

    def test_get_is_not_allowed_for_changes(self):
        c = self.campaign()
        self.assertEqual(self.client.get(reverse('bulk_email_send_batch')).status_code, 405)
        self.assertEqual(self.client.get(reverse('bulk_email_retry_failed', args=[c.pk])).status_code, 405)

    def test_non_staff_blocked(self):
        self.client.logout()
        self.client.force_login(User.objects.get(username='u1'))
        self.assertEqual(self.client.post(reverse('bulk_email_send_batch')).status_code, 302)
        self.assertEqual(len(mail.outbox), 0)

    def test_queue_down_small_audience_sends_inline(self):
        User.objects.filter(username__startswith='u').exclude(username__in=[f'u{i}' for i in range(10)]).update(is_active=False)
        c = self.draft()
        with mock.patch('django_q.tasks.async_task', side_effect=RuntimeError('no broker')):
            r = self.client.post(reverse('bulk_email_send_now', args=[c.pk]), {'confirmed': '1'}, follow=True)
        self.assertEqual(len(mail.outbox), 11)
        c.refresh_from_db()
        self.assertEqual(c.status, 'sent')

    def test_queue_down_large_audience_is_refused_and_stays_draft(self):
        c = self.draft()
        with mock.patch('django_q.tasks.async_task', side_effect=RuntimeError('no broker')):
            r = self.client.post(reverse('bulk_email_send_now', args=[c.pk]), {'confirmed': '1'}, follow=True)
        self.assertContains(r, 'too many to send during a page load')
        c.refresh_from_db()
        self.assertEqual(c.status, 'draft')
        self.assertEqual(len(mail.outbox), 0)
        self.assertIsNone(cache.get(f'bulk_email_send_{c.pk}'))

    def test_queue_down_manual_batch_is_limited_to_sync_limit(self):
        c = self.campaign()
        with mock.patch('django_q.tasks.async_task', side_effect=RuntimeError('no broker')):
            self.client.post(reverse('bulk_email_send_batch'), {})
        self.assertEqual(len(mail.outbox), 20)

    def test_retry_view_flow(self):
        c = self.campaign(status='sent')
        BulkEmailRecipient.objects.create(campaign=c, user=User.objects.get(username='u1'), status='failed', attempts=3, error='x')
        r = self.client.get(reverse('bulk_email_detail', args=[c.pk]))
        self.assertContains(r, 'Retry 1 failed')
        self.assertContains(r, '@u1')
        self.client.post(reverse('bulk_email_retry_failed', args=[c.pk]))
        c.refresh_from_db()
        self.assertEqual(c.status, 'partial')
        self.assertEqual(c.recipient_logs.get().attempts, 0)

    def test_all_pages_render(self):
        c = self.campaign()
        utils.send_bulk_email_batch(c.pk)
        d = self.draft()
        for name, args in [('bulk_email_list', []), ('bulk_email_detail', [c.pk]), ('bulk_email_detail', [d.pk]),
                           ('bulk_email_send_now', [d.pk]), ('bulk_email_create', []), ('bulk_email_edit', [d.pk]),
                           ('quick_announcement', []), ('email_template_library', []), ('email_preference_dashboard', [])]:
            r = self.client.get(reverse(name, args=args))
            self.assertEqual(r.status_code, 200, name)
        for st in ('active', 'partial', 'sending', 'sent', 'draft', 'all', 'bogus'):
            self.assertEqual(self.client.get(reverse('bulk_email_list') + f'?status={st}').status_code, 200)


class ScheduleTests(BatchBase):
    N = 3

    def test_schedule_helper_and_function_path(self):
        from django_q.models import Schedule
        s = utils.ensure_bulk_email_batch_schedule()
        self.assertEqual(utils.ensure_bulk_email_batch_schedule().pk, s.pk)
        self.assertEqual(Schedule.objects.count(), 1)
        self.assertEqual((s.schedule_type, s.repeats, s.func), ('D', -1, 'User.utils.send_bulk_email_batch'))
        self.assertEqual((s.next_run.hour, s.next_run.date()), (8, DAY1.date() + datetime.timedelta(days=1)))   # 09:00 now, so the first run is tomorrow 08:00
        # django-q resolves the dotted path and calls it with no arguments
        from django_q.tasks import async_task
        self.campaign()
        async_task('User.utils.send_bulk_email_batch')       # Q_CLUSTER sync=True in the test project
        self.assertEqual(len(mail.outbox), 4)

    def test_old_entry_point_still_works(self):
        c = self.campaign()
        self.assertEqual(utils.send_bulk_email_task(c.pk)['sent'], 4)

    def test_failed_queue_task_is_not_retried_twice(self):
        # a second batch started while the first holds the lock sends nothing
        c = self.campaign()
        cache.add(utils.BULK_LOCK_KEY, 1, 60)
        self.assertEqual(utils.send_bulk_email_task(c.pk)['stopped'], 'locked')
