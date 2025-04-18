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
        return int(self.cleaned_data['duration'])