from django import forms
from .models import UserAccount, Transaction, ProductBoost
from decimal import Decimal

class DepositForm(forms.Form):
    amount = forms.DecimalField(
        max_digits=10, 
        decimal_places=2,
        min_value=1.00,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter amount to deposit'
        })
    )

class WalletTransferForm(forms.Form):
    identifier = forms.CharField(
        max_length=254,
        label="Username or Email",
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Enter username or email address",
            "autocomplete": "off",
            "id": "id_identifier",
        }),
    )
    amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("1.00"),
        widget=forms.NumberInput(attrs={
            "class": "form-control",
            "placeholder": "Amount to send (₦)",
            "id": "id_transfer_amount",
        }),
    )
    note = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Optional note (e.g. For your order)",
        }),
    )

    def __init__(self, *args, sender_account=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.sender_account    = sender_account
        self.recipient_account = None  # populated in clean_identifier

    def clean_identifier(self):
        raw = self.cleaned_data.get("identifier", "").strip()
        if not raw:
            raise forms.ValidationError("Please enter a username or email.")

        from django.contrib.auth.models import User
        try:
            user = (
                User.objects.get(email__iexact=raw)
                if "@" in raw
                else User.objects.get(username__iexact=raw)
            )
        except User.DoesNotExist:
            raise forms.ValidationError("No account found with that username or email.")
        except User.MultipleObjectsReturned:
            raise forms.ValidationError(
                "Multiple accounts share that email. Use a username instead."
            )

        if self.sender_account and user == self.sender_account.user:
            raise forms.ValidationError("You cannot transfer funds to yourself.")

        try:
            self.recipient_account = user.account
        except Exception:
            raise forms.ValidationError("That user does not have a wallet yet.")

        return raw

    def clean_amount(self):
        amount = self.cleaned_data.get("amount")
        if amount and self.sender_account:
            if self.sender_account.balance < amount:
                raise forms.ValidationError(
                    f"Insufficient balance. "
                    f"You have ₦{self.sender_account.balance:,.2f} available."
                )
        return amount

class BoostProductForm(forms.Form):
    BOOST_CHOICES = ProductBoost.BOOST_TYPES
    DURATION_CHOICES = [
        (1, '1 Day'),
        (3, '3 Days'),
        (7, '7 Days'),
        (14, '14 Days'),
        (30, '30 Days'),
    ]
    
    boost_type = forms.ChoiceField(
        choices=BOOST_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    duration = forms.ChoiceField(
        choices=DURATION_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    def clean_duration(self):
        duration = self.cleaned_data.get('duration')
        try:
            return int(duration)
        except (ValueError, TypeError):
            raise forms.ValidationError("Invalid duration selected")
    
    def clean_boost_type(self):
        boost_type = self.cleaned_data.get('boost_type')
        valid_types = [choice[0] for choice in self.BOOST_CHOICES]
        if boost_type not in valid_types:
            raise forms.ValidationError("Invalid boost type selected")
        return boost_type