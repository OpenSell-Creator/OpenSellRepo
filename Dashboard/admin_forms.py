"""
Forms for the custom Dashboard admin pages.

Limits:
  - Percent fields are 0-100 (the model uses DecimalField(5, 2)).
  - Money fields are capped by the model's max_digits=10 (under 100,000,000.00).
  - Tier type must be unique, because UserAccount.effective_status uses
    AccountStatus.objects.filter(tier_type='free').first() and subscribe_to_tier uses
    AccountStatus.objects.get(tier_type=...), which raises when two rows share a type.
"""
from decimal import Decimal

from django import forms

from .models import AccountStatus, AffiliateProfile

MAX_BONUS = Decimal('1000000')  # a sanity cap for one manual credit


def _ctl(field, **attrs):
    field.widget.attrs.update({'class': 'ox-ctl', **attrs})


class TierAdminForm(forms.ModelForm):
    class Meta:
        model = AccountStatus
        fields = ['name', 'tier_type', 'description', 'benefits', 'monthly_price', 'two_month_price',
                  'max_listings', 'listing_discount', 'boost_discount', 'featured_listings',
                  'priority_support', 'analytics_access']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2}),
            'benefits': forms.Textarea(attrs={'rows': 4}),
            'priority_support': forms.CheckboxInput(),
            'analytics_access': forms.CheckboxInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, f in self.fields.items():
            if not isinstance(f.widget, forms.CheckboxInput):
                _ctl(f)
        for name in ('monthly_price', 'two_month_price', 'listing_discount', 'boost_discount'):
            self.fields[name].widget.attrs.update({'inputmode': 'decimal', 'step': '0.01', 'min': '0'})
        for name in ('max_listings', 'featured_listings'):
            self.fields[name].widget.attrs.update({'inputmode': 'numeric', 'min': '0'})

    def clean_name(self):
        return (self.cleaned_data.get('name') or '').strip()

    def clean_tier_type(self):
        value = self.cleaned_data.get('tier_type')
        qs = AccountStatus.objects.filter(tier_type=value)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('There is already a tier of this type. Edit that one instead.')
        return value

    def _percent(self, name):
        value = self.cleaned_data.get(name)
        if value is not None and not (0 <= value <= 100):
            raise forms.ValidationError('Use a percentage from 0 to 100.')
        return value

    def clean_listing_discount(self):
        return self._percent('listing_discount')

    def clean_boost_discount(self):
        return self._percent('boost_discount')

    def clean(self):
        data = super().clean()
        monthly, two = data.get('monthly_price'), data.get('two_month_price')
        tier = data.get('tier_type')
        if tier == 'pro' and monthly is not None and two is not None:
            if monthly <= 0 or two <= 0:
                self.add_error('monthly_price', 'A Pro tier needs a price above zero, or members get it for free.')
            elif two >= monthly * 2:
                self.add_error('two_month_price', 'The two-month price should be less than twice the monthly price, otherwise it is not a deal.')
        return data


class AffiliateSettingsForm(forms.ModelForm):
    class Meta:
        model = AffiliateProfile
        fields = ['funding_commission_rate', 'boost_commission_rate', 'subscription_commission_rate',
                  'minimum_withdrawal', 'admin_notes']
        widgets = {'admin_notes': forms.Textarea(attrs={'rows': 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            _ctl(f)
        for name in ('funding_commission_rate', 'boost_commission_rate', 'subscription_commission_rate',
                     'minimum_withdrawal'):
            self.fields[name].widget.attrs.update({'inputmode': 'decimal', 'step': '0.01', 'min': '0'})

    def _rate(self, name):
        value = self.cleaned_data.get(name)
        if value is not None and not (0 <= value <= 100):
            raise forms.ValidationError('Use a percentage from 0 to 100.')
        return value

    def clean_funding_commission_rate(self):
        return self._rate('funding_commission_rate')

    def clean_boost_commission_rate(self):
        return self._rate('boost_commission_rate')

    def clean_subscription_commission_rate(self):
        return self._rate('subscription_commission_rate')

    def clean_minimum_withdrawal(self):
        value = self.cleaned_data.get('minimum_withdrawal')
        if value is not None and value < 0:
            raise forms.ValidationError('The minimum cannot be negative.')
        return value


class BonusForm(forms.Form):
    amount = forms.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal('1'), max_value=MAX_BONUS,
        widget=forms.NumberInput(attrs={'class': 'ox-ctl', 'inputmode': 'decimal', 'step': '0.01', 'min': '1', 'placeholder': '1000'}),
    )
    reason = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={'class': 'ox-ctl', 'maxlength': 200, 'placeholder': 'Why this credit is being made', 'autocomplete': 'off'}),
    )

    def clean_reason(self):
        value = (self.cleaned_data.get('reason') or '').strip()
        if len(value) < 5:
            raise forms.ValidationError('Give a short reason, at least 5 characters.')
        return value
