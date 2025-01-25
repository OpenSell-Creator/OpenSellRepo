from django import forms
from .models import Product_Listing,Product_Image, Review
from django.forms.widgets import NumberInput
from decimal import Decimal, InvalidOperation
from .models import Category,Brand, Subcategory,Profile, Review,ReviewReply

class ListingFilterForm(forms.Form):
    category = forms.ModelChoiceField(queryset=Category.objects.all(), required=False, label='Category')
    
    def __init__(self, *args, **kwargs):
        
        super(ListingFilterForm, self).__init__(*args, **kwargs)
        self.fields['category'].widget.attrs.update({'class': 'form-control'})
        
        
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

    class Meta:
        model = Product_Listing
        fields = ['title', 'description', 'formatted_price', 'condition', 'category', 'subcategory', 'brand', 'images']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter product title'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Describe your product'}),
            'condition': forms.Select(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'subcategory': forms.Select(attrs={'class': 'form-control'}),
            'brand': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        instance = kwargs.get('instance', None)
        super().__init__(*args, **kwargs)
        if instance and instance.price:
            self.fields['formatted_price'].initial = f'₦ {instance.price:,.0f}'

        self.set_field_choices(instance)

    def set_field_choices(self, instance=None):
        categories = list(Category.objects.values_list('id', 'name'))
        if categories:
            self.fields['category'].choices = [('', 'Select Category')] + categories
        else:
            self.fields['category'].choices = [('', 'No categories available')]

        if instance and instance.category:
            subcategories = list(Subcategory.objects.filter(category=instance.category).values_list('id', 'name'))
            self.fields['subcategory'].choices = [('', 'Select Subcategory')] + subcategories if subcategories else [('', 'No subcategories available')]
        else:
            self.fields['subcategory'].choices = [('', 'Select Subcategory')]

        brands = list(Brand.objects.values_list('id', 'name'))
        if brands:
            self.fields['brand'].choices = [('', 'Select Brand')] + brands
        else:
            self.fields['brand'].choices = [('', 'No brands available')]

    def clean_formatted_price(self):
        formatted_price = self.cleaned_data.get('formatted_price')
        if formatted_price:
            try:
               return Decimal(formatted_price.replace('₦', '').replace(',', '').strip())
            except InvalidOperation:
               raise forms.ValidationError("Invalid price format")
        raise forms.ValidationError("Price is required")
        return None

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