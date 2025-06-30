from django import forms
from .models import UserAccount, Transaction, ProductBoost

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