from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from decimal import Decimal, InvalidOperation
from .models import BuyerRequest, SellerResponse, BuyerRequestImage
from Home.models import Category, Subcategory, Brand
from User.models import State, LGA,ItemReport

class MultipleFileInput(forms.ClearableFileInput):
    """Multiple file input (following existing pattern from Home.forms)"""
    allow_multiple_selected = True

class MultipleFileField(forms.FileField):
    """Multiple file field (following existing pattern from Home.forms)"""
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

class BuyerRequestForm(forms.ModelForm):
    """Main form for creating/editing buyer requests (following ListingForm pattern)"""
    
    images = MultipleFileField(required=False, help_text="Upload up to 5 images to help sellers understand what you need")
    formatted_budget_max = forms.CharField(
        label='Maximum Budget', 
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': '₦ 0',
        })
    )
    formatted_budget_min = forms.CharField(
        label='Minimum Budget', 
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': '₦ 0',
        })
    )

    class Meta:
        model = BuyerRequest
        fields = [
            'title', 'description', 'request_type', 'category', 'subcategory', 'brand',
            'service_category', 'budget_range', 'formatted_budget_min', 'formatted_budget_max', 
            'preferred_condition', 'urgency', 'needed_by', 'quantity_needed',
            'project_duration', 'skill_level_required', 'delivery_preference',
            'accept_nationwide', 'show_phone', 'contact_instructions', 'images'
        ]
        
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., iPhone 13 Pro Max 256GB or Graphic Designer for Logo',
                'maxlength': '255'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'Provide detailed information about what you need:\n• Specifications and features\n• Preferred condition or requirements\n• Any special requirements\n• Timeline for delivery'
            }),
            'request_type': forms.Select(attrs={
                'class': 'form-select',
                'id': 'id_request_type'
            }),
            'category': forms.Select(attrs={
                'class': 'form-select',
                'id': 'id_category'
            }),
            'subcategory': forms.Select(attrs={
                'class': 'form-select',
                'id': 'id_subcategory'
            }),
            'brand': forms.Select(attrs={
                'class': 'form-select'
            }),
            'service_category': forms.Select(attrs={
                'class': 'form-select',
                'id': 'id_service_category'
            }),
            'budget_range': forms.Select(attrs={
                'class': 'form-select',
                'id': 'id_budget_range'
            }),
            'preferred_condition': forms.Select(attrs={
                'class': 'form-select'
            }),
            'urgency': forms.Select(attrs={
                'class': 'form-select'
            }),
            'needed_by': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'quantity_needed': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '1',
                'min': '1'
            }),
            'project_duration': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., 2 weeks, 1 month'
            }),
            'skill_level_required': forms.Select(attrs={
                'class': 'form-select'
            }),
            'delivery_preference': forms.Select(attrs={
                'class': 'form-select'
            }),
            'contact_instructions': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Any specific instructions for contacting you (optional)'
            }),
            'show_phone': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'accept_nationwide': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }

    # Replace the __init__ method in BuyerRequestForm (around line 89-155)
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Set subcategory and brand querysets (following existing pattern)
        self.fields['subcategory'].queryset = Subcategory.objects.none()
        self.fields['brand'].queryset = Brand.objects.none()

        # Empty labels (following existing pattern)
        self.fields['category'].empty_label = "Select Category"
        self.fields['subcategory'].empty_label = "Select Subcategory"
        self.fields['brand'].empty_label = "Select Brand (Optional)"
        self.fields['service_category'].empty_label = "Select Service Category"
        self.fields['preferred_condition'].empty_label = "Any Condition"
        
        # Set initial querysets
        self.fields['category'].queryset = Category.objects.all()
        
        # Handle POST data (following existing pattern)
        if 'category' in self.data:
            try:
                category_id = int(self.data.get('category'))
                self.fields['subcategory'].queryset = Subcategory.objects.filter(
                    category_id=category_id
                )
            except (ValueError, TypeError):
                pass
                
        if 'subcategory' in self.data:
            try:
                subcategory_id = int(self.data.get('subcategory'))
                self.fields['brand'].queryset = Brand.objects.filter(
                    subcategories=subcategory_id
                )
            except (ValueError, TypeError):
                pass

        # Handle instance data (editing)
        if self.instance and self.instance.pk:
            if hasattr(self.instance, 'category') and self.instance.category:
                self.fields['subcategory'].queryset = Subcategory.objects.filter(
                    category=self.instance.category
                )
            if hasattr(self.instance, 'subcategory') and self.instance.subcategory:
                self.fields['brand'].queryset = Brand.objects.filter(
                    subcategories=self.instance.subcategory
                )
            
            # Set formatted budget fields
            if hasattr(self.instance, 'budget_min') and self.instance.budget_min:
                self.fields['formatted_budget_min'].initial = f'₦ {self.instance.budget_min:,.0f}'
            if hasattr(self.instance, 'budget_max') and self.instance.budget_max:
                self.fields['formatted_budget_max'].initial = f'₦ {self.instance.budget_max:,.0f}'
            
            # Images are optional for editing
            self.fields['images'].required = False
            self.fields['images'].help_text = "Leave empty to keep existing images"

        # Just mark fields as not required based on request type
        request_type = self.data.get('request_type') or (self.instance.request_type if self.instance and self.instance.pk else 'product')
        
        if request_type == 'product':
            # Mark service fields as not required
            self.fields['service_category'].required = False
            self.fields['project_duration'].required = False
            self.fields['skill_level_required'].required = False
            self.fields['delivery_preference'].required = False
            
        elif request_type == 'service':
            # Mark product fields as not required
            self.fields['category'].required = False
            self.fields['subcategory'].required = False
            self.fields['brand'].required = False
            self.fields['quantity_needed'].required = False
            self.fields['preferred_condition'].required = False
            
        elif request_type == 'both':
            # Both types - at least one category required but individual fields optional
            self.fields['category'].required = False
            self.fields['service_category'].required = False

    def clean_formatted_budget_min(self):
        """Clean minimum budget (following existing pattern)"""
        formatted_budget = self.cleaned_data.get('formatted_budget_min')
        if formatted_budget:
            try:
                return Decimal(formatted_budget.replace('₦', '').replace(',', '').strip())
            except InvalidOperation:
                raise forms.ValidationError("Invalid budget format")
        return None

    def clean_formatted_budget_max(self):
        """Clean maximum budget (following existing pattern)"""
        formatted_budget = self.cleaned_data.get('formatted_budget_max')
        if formatted_budget:
            try:
                return Decimal(formatted_budget.replace('₦', '').replace(',', '').strip())
            except InvalidOperation:
                raise forms.ValidationError("Invalid budget format")
        return None

    def clean(self):
        cleaned_data = super().clean()
        request_type = cleaned_data.get('request_type')
        category = cleaned_data.get('category')
        subcategory = cleaned_data.get('subcategory')
        service_category = cleaned_data.get('service_category')
        budget_range = cleaned_data.get('budget_range')
        budget_min = cleaned_data.get('formatted_budget_min')
        budget_max = cleaned_data.get('formatted_budget_max')

        # Validate request type and categories
        if request_type == 'product':
            if not category:
                self.add_error('category', 'Product category is required for product requests.')
            # Clear service category for product requests
            cleaned_data['service_category'] = None
            
        elif request_type == 'service':
            if not service_category:
                self.add_error('service_category', 'Service category is required for service requests.')
            # Clear product fields for service requests
            cleaned_data['category'] = None
            cleaned_data['subcategory'] = None
            cleaned_data['brand'] = None
            cleaned_data['quantity_needed'] = 1
            
        elif request_type == 'both':
            if not category and not service_category:
                raise forms.ValidationError("Please select at least one category for 'both' request type.")

        # Validate category and subcategory relationship
        if category and subcategory and subcategory.category != category:
            self.add_error('subcategory', 'The selected subcategory does not belong to the selected category.')

        # Validate custom budget range
        if budget_range == 'custom':
            # On edit: if the formatted fields came through empty (user didn't touch them),
            # fall back to the already-saved values on the instance so we don't wipe them.
            is_edit = self.instance and self.instance.pk
            if not budget_min and is_edit:
                budget_min = self.instance.budget_min
            if not budget_max and is_edit:
                budget_max = self.instance.budget_max

            if not budget_min or not budget_max:
                raise forms.ValidationError("Please specify both minimum and maximum budget for custom range.")

            if budget_min >= budget_max:
                raise forms.ValidationError("Maximum budget must be greater than minimum budget.")

        # Set budget fields — only populated when range is custom, cleared otherwise
        cleaned_data['budget_min'] = budget_min if budget_range == 'custom' else None
        cleaned_data['budget_max'] = budget_max if budget_range == 'custom' else None

        return cleaned_data
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.budget_min = self.cleaned_data.get('budget_min')
        instance.budget_max = self.cleaned_data.get('budget_max')
        
        if commit:
            instance.save()
        return instance

class BuyerRequestSearchForm(forms.Form):
    """Search form for buyer requests (following ProductSearchForm pattern)"""
    
    query = forms.CharField(
        label='Search', 
        max_length=100, 
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search requests...'
        })
    )
    
    request_type = forms.ChoiceField(
        choices=[('', 'All Types')] + BuyerRequest.REQUEST_TYPES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    category = forms.ModelChoiceField(
        queryset=Category.objects.all(), 
        required=False, 
        empty_label="All Categories",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    subcategory = forms.ModelChoiceField(
        queryset=Subcategory.objects.none(), 
        required=False, 
        empty_label="All Subcategories",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    brand = forms.ModelChoiceField(
        queryset=Brand.objects.none(), 
        required=False, 
        empty_label="All Brands",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    service_category = forms.ChoiceField(
        choices=[('', 'All Service Categories')] + BuyerRequest.SERVICE_CATEGORIES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    budget_range = forms.ChoiceField(
        choices=[('', 'Any Budget')] + BuyerRequest.BUDGET_RANGE_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    urgency = forms.ChoiceField(
        choices=[('', 'Any Urgency')] + BuyerRequest.URGENCY_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    condition = forms.ChoiceField(
        choices=[('', 'Any Condition')] + BuyerRequest.CONDITION_CHOICES,
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
        label="Verified Buyers Only",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set dynamic querysets (following existing pattern)
        self.fields['subcategory'].queryset = Subcategory.objects.none()
        self.fields['brand'].queryset = Brand.objects.none()
        self.fields['lga'].queryset = LGA.objects.none()

        category_id = self.data.get('category', None)
        if category_id:
            try:
                category = Category.objects.get(id=category_id)
                self.fields['subcategory'].queryset = Subcategory.objects.filter(category_id=category_id)
                self.fields['brand'].queryset = Brand.objects.filter(categories=category)
            except Category.DoesNotExist:
                pass
        else:
            self.fields['brand'].queryset = Brand.objects.all()

        state_id = self.data.get('state', None)
        if state_id:
            self.fields['lga'].queryset = LGA.objects.filter(state_id=state_id)

class SellerResponseForm(forms.ModelForm):
    """Form for sellers to respond to buyer requests"""
    
    class Meta:
        model = SellerResponse
        fields = [
            'response_type', 'related_product', 'related_service',
            'message', 'offered_price', 'availability', 'condition_offered',
            'quantity_available', 'delivery_time', 'service_includes',
            'additional_info', 'contact_phone', 'contact_email', 'preferred_contact'
        ]
        
        widgets = {
            'response_type': forms.Select(attrs={
                'class': 'form-select',
                'id': 'id_response_type'
            }),
            'related_product': forms.Select(attrs={
                'class': 'form-select'
            }),
            'related_service': forms.Select(attrs={
                'class': 'form-select'
            }),
            'message': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'Describe what you can offer:\n• Product/service details\n• Your experience or credentials\n• Why you\'re the right choice\n• Any guarantees or assurances'
            }),
            'offered_price': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '₦ 0.00',
                'step': '0.01'
            }),
            'availability': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Available immediately, Within 2 days, etc.'
            }),
            'condition_offered': forms.Select(attrs={
                'class': 'form-select'
            }),
            'quantity_available': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Quantity available',
                'min': '1'
            }),
            'delivery_time': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., 2-3 business days, 1 week'
            }),
            'service_includes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'What\'s included in your service offering?'
            }),
            'additional_info': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Any additional information or special terms'
            }),
            'contact_phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Your phone number (optional)'
            }),
            'contact_email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Your email address (optional)'
            }),
            'preferred_contact': forms.Select(attrs={
                'class': 'form-select'
            }),
        }

    def __init__(self, *args, **kwargs):
        self.buyer_request = kwargs.pop('buyer_request', None)
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # ── Related item querysets ────────────────────────────────────────
        self.fields['related_product'].required = False
        self.fields['related_service'].required = False
        self.fields['related_product'].empty_label = "Select your product (optional)"
        self.fields['related_service'].empty_label = "Select your service (optional)"

        if self.user and hasattr(self.user, 'profile'):
            profile = self.user.profile
            try:
                from Home.models import Product_Listing
                self.fields['related_product'].queryset = Product_Listing.objects.filter(
                    seller=profile,
                    is_suspended=False
                )
            except Exception:
                from Home.models import Product_Listing
                self.fields['related_product'].queryset = Product_Listing.objects.none()

            try:
                from Services.models import ServiceListing
                self.fields['related_service'].queryset = ServiceListing.objects.filter(
                    provider=profile,
                    is_active=True,
                    is_suspended=False
                )
            except Exception:
                from Services.models import ServiceListing
                self.fields['related_service'].queryset = ServiceListing.objects.none()
        else:
            from Home.models import Product_Listing
            from Services.models import ServiceListing
            self.fields['related_product'].queryset = Product_Listing.objects.none()
            self.fields['related_service'].queryset = ServiceListing.objects.none()

        # ── All optional fields ───────────────────────────────────────────
        optional_fields = [
            'offered_price', 'condition_offered', 'quantity_available',
            'delivery_time', 'service_includes', 'availability',
            'additional_info', 'contact_phone', 'contact_email',
        ]
        for field_name in optional_fields:
            if field_name in self.fields:
                self.fields[field_name].required = False

        # ── Pre-fill contact info ─────────────────────────────────────────
        if self.user and hasattr(self.user, 'profile') and not self.instance.pk:
            profile = self.user.profile
            self.fields['contact_phone'].initial = profile.phone_number
            self.fields['contact_email'].initial = self.user.email

        # ── Adjust visible fields based on buyer request type ────────────
        if self.buyer_request:
            request_type = self.buyer_request.request_type

            # For service-only requests: hide product field, remove product-only fields
            if request_type == 'service':
                self.fields['related_product'].widget = forms.HiddenInput()
                self.fields.pop('condition_offered', None)
                self.fields.pop('quantity_available', None)

            # For product-only requests: hide service field, remove service-only fields
            elif request_type == 'product':
                self.fields['related_service'].widget = forms.HiddenInput()
                self.fields.pop('delivery_time', None)
                self.fields.pop('service_includes', None)

            # For 'both': show everything, nothing hidden
            # quantity_available: only show if buyer needs more than 1
            if self.buyer_request.quantity_needed <= 1:
                self.fields.pop('quantity_available', None)

            # Pre-fill condition preference
            if (self.buyer_request.preferred_condition != 'any'
                    and 'condition_offered' in self.fields):
                self.fields['condition_offered'].initial = self.buyer_request.preferred_condition
        
        if not self.instance.pk:
            request_type = getattr(self.buyer_request, 'request_type', 'product') if self.buyer_request else 'product'
            if request_type == 'service':
                self.fields['response_type'].initial = 'custom_service'
            else:
                self.fields['response_type'].initial = 'custom_product'

    def clean_offered_price(self):
        offered_price = self.cleaned_data.get('offered_price')
        
        if offered_price is not None and offered_price <= 0:
            raise ValidationError("Offered price must be greater than zero.")
        
        return offered_price
    
    def clean_quantity_available(self):
        quantity = self.cleaned_data.get('quantity_available')
        
        if quantity and self.buyer_request and self.buyer_request.quantity_needed:
            if quantity < self.buyer_request.quantity_needed:
                self.add_error('quantity_available', 
                    f"Buyer needs {self.buyer_request.quantity_needed} items. "
                    f"Please specify at least this quantity or contact the buyer directly."
                )
        
        return quantity

    # buyer_requests/forms.py — REPLACE SellerResponseForm.clean() entirely

    def clean(self):
        cleaned_data = super().clean()
        response_type    = cleaned_data.get('response_type')
        related_product  = cleaned_data.get('related_product')
        related_service  = cleaned_data.get('related_service')

        # If the field was hidden (not in self.fields), force its value to None
        # so hidden empty-string submissions never trigger validation errors.
        if 'related_product' not in self.fields:
            cleaned_data['related_product'] = None
            related_product = None

        if 'related_service' not in self.fields:
            cleaned_data['related_service'] = None
            related_service = None

        # Require a linked product only when seller explicitly says they have one
        if response_type == 'existing_product' and not related_product:
            self.add_error(
                'related_product',
                'Please select one of your products that matches this request.'
            )

        # Require a linked service only when seller explicitly says they offer one
        if response_type == 'existing_service' and not related_service:
            self.add_error(
                'related_service',
                'Please select one of your services that matches this request.'
            )

        # Hybrid: require at least one linked item
        if response_type == 'hybrid':
            if not related_product and not related_service:
                raise forms.ValidationError(
                    'For a hybrid response, please link at least one of your '
                    'existing products or services.'
                )

        return cleaned_data

class RequestFilterForm(forms.Form):
    """Simple filter form for request listings"""
    
    category = forms.ModelChoiceField(
        queryset=Category.objects.all(), 
        required=False, 
        label='Category',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    request_type = forms.ChoiceField(
        choices=[('', 'All Types')] + BuyerRequest.REQUEST_TYPES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    def __init__(self, *args, **kwargs):
        super(RequestFilterForm, self).__init__(*args, **kwargs)
        self.fields['category'].widget.attrs.update({'class': 'form-select'})