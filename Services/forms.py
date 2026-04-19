from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from decimal import Decimal, InvalidOperation
from .models import (
    ServiceListing, ServiceInquiry, ServiceReview, ServiceReviewReply,
    ServiceImage, ServiceDocument
)
from User.models import State, LGA


class MultipleFileInput(forms.ClearableFileInput):
    """Multiple file input (following existing pattern)"""
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    """Multiple file field (following existing pattern)"""
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = single_file_clean(data, initial)
        return result


class ServiceListingForm(forms.ModelForm):
    """Main form for creating/editing service listings"""

    images = MultipleFileField(required=False, help_text="Upload up to 5 images showcasing your work")
    documents = MultipleFileField(required=False, help_text="Upload certificates, portfolio samples (PDF, DOC, images)")

    base_price = forms.CharField(
        label='Base Price',
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '₦ 0',
        })
    )
    min_price = forms.CharField(
        label='Minimum Price',
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '₦ 0',
        })
    )
    max_price = forms.CharField(
        label='Maximum Price',
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '₦ 0',
        })
    )

    class Meta:
        model = ServiceListing
        fields = [
            'title', 'description', 'service_type', 'category',
            'pricing_type', 'base_price', 'min_price', 'max_price',
            'experience_level', 'availability', 'delivery_method', 'delivery_time',
            'revision_limit', 'delivery_days',
            'languages', 'skills_offered', 'tools_used', 'requirements',
            'what_you_get', 'extra_services', 'portfolio_url', 'certifications',
            'serves_nationwide', 'contact_instructions'
        ]

        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Professional Logo Design, Website Development, House Cleaning',
                'maxlength': '255'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 6,
                'placeholder': 'Describe your service in detail:\n• What you offer\n• Your expertise and experience\n• What makes you stand out\n• Your working process'
            }),
            'service_type': forms.Select(attrs={'class': 'form-select'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'pricing_type': forms.Select(attrs={
                'class': 'form-select',
                'id': 'id_pricing_type'
            }),
            'experience_level': forms.Select(attrs={'class': 'form-select'}),
            'availability': forms.Select(attrs={'class': 'form-select'}),
            'delivery_method': forms.Select(attrs={'class': 'form-select'}),
            'delivery_time': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., 3-5 days, 1 week, Same day'
            }),
            'revision_limit': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Number of revisions included',
                'min': '0',
                'max': '10',
                'value': '2'
            }),
            'delivery_days': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Expected delivery time in days',
                'min': '1',
                'max': '365',
                'value': '7'
            }),
            'languages': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., English, Yoruba, Hausa, Igbo'
            }),
            'skills_offered': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'List your main skills (e.g., Graphic Design, Photoshop, Illustrator)'
            }),
            'tools_used': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Tools, software, or equipment you use (optional)'
            }),
            'requirements': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'What do you need from clients to get started? (optional)'
            }),
            'what_you_get': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'What will clients receive? List deliverables (optional)'
            }),
            'extra_services': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Additional services you can provide (optional)'
            }),
            'portfolio_url': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://your-portfolio.com (optional)'
            }),
            'certifications': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'List your relevant certifications or qualifications (optional)'
            }),
            'contact_instructions': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Any specific instructions for contacting you (optional)'
            }),
            'serves_nationwide': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        self.fields['category'].empty_label = "Select Service Category"

        if not self.instance.pk:
            self.fields['revision_limit'].initial = 2
            self.fields['delivery_days'].initial = 7

        if self.instance and self.instance.pk:
            if hasattr(self.instance, 'base_price') and self.instance.base_price:
                self.fields['base_price'].initial = f'₦ {self.instance.base_price:,.0f}'
            if hasattr(self.instance, 'min_price') and self.instance.min_price:
                self.fields['min_price'].initial = f'₦ {self.instance.min_price:,.0f}'
            if hasattr(self.instance, 'max_price') and self.instance.max_price:
                self.fields['max_price'].initial = f'₦ {self.instance.max_price:,.0f}'

            self.fields['images'].required = False
            self.fields['documents'].required = False
            self.fields['images'].help_text = "Leave empty to keep existing images"
            self.fields['documents'].help_text = "Leave empty to keep existing documents"

    def clean_base_price(self):
        formatted_price = self.cleaned_data.get('base_price')
        if formatted_price:
            try:
                cleaned = formatted_price.replace('₦', '').replace(',', '').strip()
                if cleaned:
                    return Decimal(cleaned)
            except (InvalidOperation, ValueError) as e:
                raise forms.ValidationError(f"Invalid price format: {str(e)}")
        return None

    def clean_min_price(self):
        formatted_price = self.cleaned_data.get('min_price')
        if formatted_price:
            try:
                cleaned = formatted_price.replace('₦', '').replace(',', '').strip()
                if cleaned:
                    return Decimal(cleaned)
            except (InvalidOperation, ValueError) as e:
                raise forms.ValidationError(f"Invalid price format: {str(e)}")
        return None

    def clean_max_price(self):
        formatted_price = self.cleaned_data.get('max_price')
        if formatted_price:
            try:
                cleaned = formatted_price.replace('₦', '').replace(',', '').strip()
                if cleaned:
                    return Decimal(cleaned)
            except (InvalidOperation, ValueError) as e:
                raise forms.ValidationError(f"Invalid price format: {str(e)}")
        return None

    def clean_revision_limit(self):
        revision_limit = self.cleaned_data.get('revision_limit')
        if revision_limit is None:
            return 2
        return revision_limit

    def clean_delivery_days(self):
        delivery_days = self.cleaned_data.get('delivery_days')
        if delivery_days is None:
            return 7
        return delivery_days

    def clean(self):
        cleaned_data = super().clean()
        pricing_type = cleaned_data.get('pricing_type')
        base_price = cleaned_data.get('base_price')
        min_price = cleaned_data.get('min_price')
        max_price = cleaned_data.get('max_price')

        is_edit = self.instance and self.instance.pk

        # On edit, if the formatted price fields came through empty (user didn't
        # touch them), fall back to the already-saved values so we don't wipe them.
        if is_edit:
            if not base_price and self.instance.base_price:
                base_price = self.instance.base_price
                cleaned_data['base_price'] = base_price
            if not min_price and self.instance.min_price:
                min_price = self.instance.min_price
                cleaned_data['min_price'] = min_price
            if not max_price and self.instance.max_price:
                max_price = self.instance.max_price
                cleaned_data['max_price'] = max_price

        if pricing_type in ['fixed', 'hourly', 'project', 'package']:
            if not base_price:
                self.add_error('base_price', f'Base price is required for {pricing_type} pricing.')

        elif pricing_type == 'negotiable':
            if min_price and max_price:
                if min_price >= max_price:
                    raise forms.ValidationError("Maximum price must be greater than minimum price.")

        if 'revision_limit' not in cleaned_data or cleaned_data.get('revision_limit') is None:
            cleaned_data['revision_limit'] = 2

        if 'delivery_days' not in cleaned_data or cleaned_data.get('delivery_days') is None:
            cleaned_data['delivery_days'] = 7

        return cleaned_data


class ServiceSearchForm(forms.Form):
    """Search form for services"""

    query = forms.CharField(
        label='Search Services',
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search for services or skills...'
        })
    )

    service_type = forms.ChoiceField(
        choices=[('', 'All Types')] + ServiceListing.SERVICE_TYPES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    category = forms.ChoiceField(
        choices=[('', 'All Categories')] + ServiceListing.SERVICE_CATEGORIES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    pricing_type = forms.ChoiceField(
        choices=[('', 'Any Pricing')] + ServiceListing.PRICING_TYPES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    min_price = forms.DecimalField(
        min_value=0,
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Min Price'
        })
    )

    max_price = forms.DecimalField(
        min_value=0,
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Max Price'
        })
    )

    experience_level = forms.ChoiceField(
        choices=[('', 'Any Experience')] + ServiceListing.EXPERIENCE_LEVELS,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    availability = forms.ChoiceField(
        choices=[('', 'Any Availability')] + ServiceListing.AVAILABILITY_TYPES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    delivery_method = forms.ChoiceField(
        choices=[('', 'Any Delivery')] + ServiceListing.DELIVERY_METHODS,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    state = forms.ModelChoiceField(
        queryset=State.objects.all(),
        required=False,
        empty_label="All States",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    lga = forms.ModelChoiceField(
        queryset=LGA.objects.none(),
        required=False,
        empty_label="All LGAs",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    verified_only = forms.BooleanField(
        required=False,
        label="Verified Providers Only",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['lga'].queryset = LGA.objects.none()
        state_id = self.data.get('state', None)
        if state_id:
            self.fields['lga'].queryset = LGA.objects.filter(state_id=state_id)


class ServiceInquiryForm(forms.ModelForm):
    """
    Form for clients to inquire about services.
    This is the STRUCTURED inquiry form — separate from free-form messaging.
    Used by: services:create_inquiry view → inquiry_detail → respond_to_inquiry
    """

    class Meta:
        model = ServiceInquiry
        fields = [
            'message', 'budget', 'timeline', 'requirements',
            'contact_phone', 'contact_email', 'preferred_contact'
        ]

        widgets = {
            'message': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': (
                    'Describe your project or requirement in detail:\n'
                    '• What you need\n'
                    '• Project scope\n'
                    '• Your expectations\n'
                    '• Any specific requirements'
                )
            }),
            'budget': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '₦ 0.00',
                'step': '0.01'
            }),
            'timeline': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., ASAP, Within 1 week, Flexible'
            }),
            'requirements': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Any specific requirements or preferences (optional)'
            }),
            'contact_phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Your phone number (optional)'
            }),
            'contact_email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Your email address (optional)'
            }),
            'preferred_contact': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        self.service = kwargs.pop('service', None)
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if self.user and hasattr(self.user, 'profile'):
            profile = self.user.profile
            if not self.instance.pk:
                self.fields['contact_phone'].initial = profile.phone_number
                self.fields['contact_email'].initial = self.user.email

    def clean_budget(self):
        budget = self.cleaned_data.get('budget')
        if budget is not None and budget <= 0:
            raise ValidationError("Budget must be greater than zero.")
        return budget


class ServiceReviewForm(forms.ModelForm):
    """Form for service reviews"""

    class Meta:
        model = ServiceReview
        fields = [
            'rating', 'review_text', 'communication_rating',
            'quality_rating', 'timeliness_rating'
        ]
        widgets = {
            'rating': forms.Select(
                choices=[(i, f'{i} Star{"s" if i != 1 else ""}') for i in range(1, 6)],
                attrs={'class': 'form-select'}
            ),
            'review_text': forms.Textarea(attrs={
                'rows': 4,
                'class': 'form-control',
                'placeholder': 'Share your experience with this service provider...'
            }),
            'communication_rating': forms.Select(
                choices=[(i, f'{i} Star{"s" if i != 1 else ""}') for i in range(1, 6)],
                attrs={'class': 'form-select'}
            ),
            'quality_rating': forms.Select(
                choices=[(i, f'{i} Star{"s" if i != 1 else ""}') for i in range(1, 6)],
                attrs={'class': 'form-select'}
            ),
            'timeliness_rating': forms.Select(
                choices=[(i, f'{i} Star{"s" if i != 1 else ""}') for i in range(1, 6)],
                attrs={'class': 'form-select'}
            ),
        }


class ServiceReviewReplyForm(forms.ModelForm):
    """Form for service review replies"""

    class Meta:
        model = ServiceReviewReply
        fields = ['reply_text']
        widgets = {
            'reply_text': forms.Textarea(attrs={
                'rows': 3,
                'class': 'form-control',
                'placeholder': 'Reply to this review...'
            }),
        }


class QuickInquiryForm(forms.Form):
    """Quick inquiry form for AJAX requests"""

    message = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Send a quick message about your project...'
        })
    )

    budget = forms.DecimalField(
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Your budget (optional)'
        })
    )

    phone = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Your phone number (optional)'
        })
    )


class ServiceFilterForm(forms.Form):
    """Simple filter form for service listings"""

    category = forms.ChoiceField(
        choices=[('', 'All Categories')] + ServiceListing.SERVICE_CATEGORIES,
        required=False,
        label='Category',
        widget=forms.Select(attrs={'class': 'form-select'})
    )


class InquiryResponseForm(forms.ModelForm):
    """
    Form for service providers to respond to inquiries.
    Used by: services:respond_to_inquiry view
    This is the STRUCTURED response form — separate from free-form messaging.
    """

    class Meta:
        model = ServiceInquiry
        fields = ['provider_response', 'provider_quote', 'status']

        widgets = {
            'provider_response': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Respond to the client inquiry...'
            }),
            'provider_quote': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '₦ 0.00',
                'step': '0.01'
            }),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }

    def clean_provider_quote(self):
        quote = self.cleaned_data.get('provider_quote')
        if quote is not None and quote <= 0:
            raise ValidationError("Quote must be greater than zero.")
        return quote