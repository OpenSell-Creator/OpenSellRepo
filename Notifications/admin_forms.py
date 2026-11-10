"""
Forms for the Notifications admin pages.

Limits and why:
  - title 100: Notification.title allows 255, but web-push titles are cut by browsers at roughly
    50 to 80 characters, so 100 keeps the first line readable everywhere.
  - message 1000: push bodies are cut far earlier; the full text only shows in the inbox.
  - action_text 50: the model column is max_length=50.
  - action_url: a site path ("/boost/") or an https address. Anything else (javascript:, data:,
    http://) is refused because the inbox renders it as a link.
"""
import re

from django import forms
from django.contrib.auth.models import User

from .models import NotificationCategory, NotificationPriority

AUDIENCES = [
    ('users', 'Specific people'),
    ('affiliates', 'Active affiliates'),
    ('pro', 'Pro tier members'),
    ('staff', 'Staff'),
    ('all', 'Everyone'),
]
MAX_NAMES = 200
NAME_SPLIT = re.compile(r'[,\s]+')


class ComposeForm(forms.Form):
    audience = forms.ChoiceField(choices=AUDIENCES, initial='users')
    usernames = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'ox-ctl', 'rows': 2, 'placeholder': 'ada, tunde, ...'}),
    )
    title = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'ox-ctl', 'maxlength': 100, 'autocomplete': 'off'}),
    )
    message = forms.CharField(
        max_length=1000,
        widget=forms.Textarea(attrs={'class': 'ox-ctl', 'rows': 4, 'maxlength': 1000}),
    )
    category = forms.ChoiceField(choices=NotificationCategory.choices, initial=NotificationCategory.ANNOUNCEMENT,
                                 widget=forms.Select(attrs={'class': 'ox-ctl'}))
    priority = forms.ChoiceField(choices=NotificationPriority.choices, initial=NotificationPriority.NORMAL,
                                 widget=forms.Select(attrs={'class': 'ox-ctl'}))
    action_url = forms.CharField(
        required=False, max_length=500,
        widget=forms.TextInput(attrs={'class': 'ox-ctl', 'placeholder': '/dashboard/boost/status/', 'inputmode': 'url', 'autocomplete': 'off'}),
    )
    action_text = forms.CharField(
        required=False, max_length=50,
        widget=forms.TextInput(attrs={'class': 'ox-ctl', 'maxlength': 50, 'placeholder': 'Open'}),
    )
    push = forms.BooleanField(required=False, initial=True)

    def __init__(self, *args, allow_all=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.allow_all = allow_all
        self.users = None  # resolved for audience == 'users'
        if not allow_all:
            self.fields['audience'].choices = [c for c in AUDIENCES if c[0] != 'all']

    def clean_title(self):
        value = (self.cleaned_data.get('title') or '').strip()
        if len(value) < 3:
            raise forms.ValidationError('Give it a title of at least 3 characters.')
        return value

    def clean_message(self):
        value = (self.cleaned_data.get('message') or '').strip()
        if len(value) < 5:
            raise forms.ValidationError('The message needs at least 5 characters.')
        return value

    def clean_action_url(self):
        url = (self.cleaned_data.get('action_url') or '').strip()
        if not url:
            return ''
        if url.startswith('/') and not url.startswith('//') and '\\' not in url:
            return url
        if url.lower().startswith('https://'):
            return url
        raise forms.ValidationError('Use a site path starting with / or a full https:// address.')

    def clean(self):
        data = super().clean()
        if data.get('action_url') and not (data.get('action_text') or '').strip():
            self.add_error('action_text', 'Add the button text that goes with the link.')
        if data.get('audience') == 'all' and not self.allow_all:
            self.add_error('audience', 'Only a superuser can send to everyone.')
        if data.get('audience') == 'users':
            names = [n for n in NAME_SPLIT.split(data.get('usernames') or '') if n]
            if not names:
                self.add_error('usernames', 'Type at least one username.')
            elif len(names) > MAX_NAMES:
                self.add_error('usernames', f'That is {len(names)} names. Use an audience group above {MAX_NAMES}.')
            else:
                found = {u.username.lower(): u for u in User.objects.filter(is_active=True, username__in=names)}
                # username lookups are case-sensitive on some databases, so match case-insensitively too
                if len(found) < len({n.lower() for n in names}):
                    for u in User.objects.filter(is_active=True, username__iregex=r'^(' + '|'.join(re.escape(n) for n in names) + r')$'):
                        found.setdefault(u.username.lower(), u)
                missing = sorted({n for n in names if n.lower() not in found})
                if missing:
                    self.add_error('usernames', 'No active user named: ' + ', '.join(missing[:10]) + ('...' if len(missing) > 10 else ''))
                else:
                    self.users = list(found.values())
        return data
