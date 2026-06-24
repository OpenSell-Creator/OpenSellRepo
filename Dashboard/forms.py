from django import forms
from .models import UserAccount, Transaction, ProductBoost, WithdrawalRequest, MonnifyTransaction
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
    
### forms.py — ADD new class WithdrawalRequestForm (after WalletTransferForm, before BoostProductForm)

class WithdrawalRequestForm(forms.Form):
    """
    User-facing withdrawal request form. Does NOT save directly —
    call WithdrawalRequest.create_for_user() with the cleaned_data
    from the view. This form only validates input and previews fee/payout.
    """
    requested_amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("100.00"),
        widget=forms.NumberInput(attrs={
            "class": "form-control",
            "placeholder": "Amount to withdraw (₦)",
            "id": "id_requested_amount",
        }),
    )
    bank_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "e.g. GTBank, Access Bank",
        }),
    )
    account_number = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "10-digit account number",
        }),
    )
    account_name = forms.CharField(
        max_length=255,
        help_text="Must match your verified identity on OpenSell",
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Account holder's full name",
        }),
    )

    proof_type = forms.ChoiceField(
        choices=WithdrawalRequest.PROOF_TYPE_CHOICES,
        initial='monnify_reference',
        widget=forms.RadioSelect(attrs={"class": "proof-type-radio"}),
    )
    monnify_transaction = forms.ModelChoiceField(
        queryset=MonnifyTransaction.objects.none(),
        required=False,
        label="Select your deposit transaction",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    monnify_reference_manual = forms.CharField(
        max_length=100,
        required=False,
        label="Or enter Monnify reference manually",
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "e.g. MNFY|0|20240601...",
        }),
    )
    proof_upload = forms.FileField(
        required=False,
        label="Or upload bank debit alert",
        widget=forms.ClearableFileInput(attrs={"class": "form-control"}),
    )
    proof_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            "class": "form-control",
            "rows": 3,
            "placeholder": "Any additional notes about your proof (optional)",
        }),
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.account = getattr(user, "account", None) if user else None
        self._fee_amount = None
        self._net_payout = None

        if self.account:
            self.fields["monnify_transaction"].queryset = (
                MonnifyTransaction.objects
                .filter(user_account=self.account, payment_status="PAID")
                .order_by("-paid_on")
            )

    def clean_requested_amount(self):
        amount = self.cleaned_data.get("requested_amount")
        if amount and self.account:
            if amount > self.account.withdrawable_balance:
                raise forms.ValidationError(
                    f"Requested amount (₦{amount:,.2f}) exceeds your withdrawable "
                    f"balance (₦{self.account.withdrawable_balance:,.2f})."
                )
        return amount

    def clean(self):
        cleaned_data = super().clean()

        # Only one active withdrawal request at a time
        if self.account and self.account.has_pending_withdrawal:
            raise forms.ValidationError(
                "You already have a pending or under-review withdrawal request. "
                "Please wait for it to be resolved before submitting a new one."
            )

        # At least one form of proof required
        monnify_transaction = cleaned_data.get("monnify_transaction")
        monnify_reference_manual = cleaned_data.get("monnify_reference_manual")
        proof_upload = cleaned_data.get("proof_upload")

        if not monnify_transaction and not monnify_reference_manual and not proof_upload:
            raise forms.ValidationError(
                "You must provide proof of the original deposit: either select your "
                "Monnify transaction, enter the Monnify reference number, or upload a "
                "bank debit alert."
            )

        # Compute fee/net payout preview once amount is valid
        requested_amount = cleaned_data.get("requested_amount")
        if requested_amount:
            fee_rate = WithdrawalRequest.DEFAULT_FEE_RATE
            self._fee_amount = (requested_amount * fee_rate / 100).quantize(Decimal("0.01"))
            self._net_payout = requested_amount - self._fee_amount

        return cleaned_data

    @property
    def fee_amount(self):
        """Live fee preview — available after clean(). None if not yet computed."""
        return self._fee_amount

    @property
    def net_payout(self):
        """Live net payout preview — available after clean(). None if not yet computed."""
        return self._net_payout
    
class WithdrawalAdminActionForm(forms.Form):
    """Used by admin's reject action to collect a rejection reason."""
    rejection_reason = forms.CharField(
        label="Reason for rejection",
        widget=forms.Textarea(attrs={
            "class": "form-control",
            "rows": 4,
            "placeholder": "Explain why this withdrawal request is being rejected...",
        }),
    )