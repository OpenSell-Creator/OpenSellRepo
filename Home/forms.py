from django import forms
from .models import Product_Listing,Product_Image, Review
from django.forms.widgets import NumberInput
from decimal import Decimal, InvalidOperation
from .models import Category,Brand, Subcategory,Profile, Review,ReviewReply

class ListingFilterForm(forms.Form):
    category = forms.ModelChoiceField(queryset=Category.objects.all(), required=False, label='Category')
    
    def __init__(self, *args, **kwargs):
        
        super(ListingFilterForm, self).__init__(*args, **kwargs)
        self.fields['category'].widget.attrs.update({'class': 'form-select'})
               
class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True
    
class MultipleFileField(forms.FileField):
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

class FormattedPriceInput(forms.NumberInput):
    def format_value(self, value):
        if value is None:
            return ''
        return '₦ {:,.0f}'.format(Decimal(value))
    
class ListingForm(forms.ModelForm):
    images = MultipleFileField(required=False)
    formatted_price = forms.CharField(label='Price', required=True)
    
    LISTING_TYPE_CHOICES = [
        ('standard', 'Standard Listing (7 days) - Free'),
        ('premium', 'Premium Listing (30 days) - ₦500'),
        ('emergency', 'Emergency Sale (3 days) - Free'),
        ('permanent', 'Permanent Retail Listing - ₦1000/month'),
    ]
    
    listing_type = forms.ChoiceField(
        choices=LISTING_TYPE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    quantity = forms.IntegerField(
        min_value=1, 
        initial=1,
        widget=forms.NumberInput(attrs={'class': 'form-select'})
    )
    
    is_always_available = forms.BooleanField(
        required=False, 
        label='Always Available',
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'data-toggle': 'tooltip',
            'title': 'Products marked as always available will not be removed from listings'
        })
    )

    class Meta:
        model = Product_Listing
        fields = ['title', 'description', 'formatted_price', 'condition', 
                 'category', 'subcategory', 'brand', 'images', 'listing_type', 
                 'quantity', 'is_always_available']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'condition': forms.Select(attrs={'class': 'form-select'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'subcategory': forms.Select(attrs={'class': 'form-select'}),
            'brand': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Initialize with empty querysets
        self.fields['subcategory'].queryset = Subcategory.objects.none()
        self.fields['brand'].queryset = Brand.objects.none()
        
        # Add empty choice for all select fields
        self.fields['category'].empty_label = "Select Category"
        self.fields['subcategory'].empty_label = "Select Subcategory"
        self.fields['brand'].empty_label = "Select Brand"
        self.fields['condition'].empty_label = "Select Condition"
        
        # Set initial querysets
        self.fields['category'].queryset = Category.objects.all()
        
        # Handle POST data
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

        # Handle existing instance
        if self.instance and self.instance.pk:
            if hasattr(self.instance, 'category') and self.instance.category:
                self.fields['subcategory'].queryset = Subcategory.objects.filter(
                    category=self.instance.category
                )
            if hasattr(self.instance, 'subcategory') and self.instance.subcategory:
                self.fields['brand'].queryset = Brand.objects.filter(
                    subcategories=self.instance.subcategory
                )
            if hasattr(self.instance, 'price') and self.instance.price:
                self.fields['formatted_price'].initial = f'₦ {self.instance.price:,.0f}'
            
            self.fields['quantity'].required = self.instance.listing_type != 'permanent'


    def clean_formatted_price(self):
        formatted_price = self.cleaned_data.get('formatted_price')
        if formatted_price:
            try:
                return Decimal(formatted_price.replace('₦', '').replace(',', '').strip())
            except InvalidOperation:
                raise forms.ValidationError("Invalid price format")
        raise forms.ValidationError("Price is required")

    def clean(self):
        cleaned_data = super().clean()
        category = cleaned_data.get('category')
        subcategory = cleaned_data.get('subcategory')

        if category and subcategory and subcategory.category != category:
            self.add_error('subcategory', 'The selected subcategory does not belong to the selected category.')

        # Set the price field
        cleaned_data['price'] = cleaned_data.get('formatted_price')

        return cleaned_data
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.price = self.cleaned_data.get('price')
        if commit:
           instance.save()
        return instance
        
class ProductSearchForm(forms.Form):
    query = forms.CharField(label='Search', max_length=100, required=False)
    category = forms.ModelChoiceField(queryset=Category.objects.all(), required=False, empty_label="All Categories")
    subcategory = forms.ModelChoiceField(queryset=Subcategory.objects.none(), required=False, empty_label="All Subcategories")
    min_price = forms.DecimalField(min_value=0, required=False)
    max_price = forms.DecimalField(min_value=0, required=False)
    condition = forms.ChoiceField(choices=[('', 'Any')] + Product_Listing.CONDITION_CHOICES, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['subcategory'].queryset = Subcategory.objects.none()

        if 'category' in self.data:
            try:
                category_id = int(self.data.get('category'))
                self.fields['subcategory'].queryset = Subcategory.objects.filter(category_id=category_id)
            except (ValueError, TypeError):
                pass
    
class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ['rating', 'comment']
        widgets = {
            'rating': forms.Select(choices=[(i, str(i)) for i in range(1, 6)]),
            'comment': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }

class ReviewReplyForm(forms.ModelForm):
    class Meta:
        model = ReviewReply
        fields = ['comment']
        widgets = {
            'comment': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }