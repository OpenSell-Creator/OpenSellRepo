from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Location, Profile, LGA, BusinessVerificationDocument
import re

class SignUpForm(UserCreationForm):
    email = forms.EmailField(
        label="", 
        required=False, 
        widget=forms.EmailInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Email Address (Optional)'
        })
    )
    first_name = forms.CharField(
        label="", 
        max_length=100, 
        required=False, 
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'First Name (Optional)'
        })
    )
    last_name = forms.CharField(
        label="", 
        max_length=100, 
        required=False, 
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Last Name (Optional)'
        })
    )

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super(SignUpForm, self).__init__(*args, **kwargs)

        self.fields['username'].widget.attrs['class'] = 'form-control'
        self.fields['username'].widget.attrs['placeholder'] = 'User Name'
        self.fields['username'].label = ''
        self.fields['username'].help_text = 'Required. Letters, digits and symbols (@/./+/-/_) only.'

        self.fields['password1'].widget.attrs['class'] = 'form-control'
        self.fields['password1'].widget.attrs['placeholder'] = 'Password'
        self.fields['password1'].label = ''
        self.fields['password1'].help_text = 'Choose any password - minimum 6 characters.'

        self.fields['password2'].widget.attrs['class'] = 'form-control'
        self.fields['password2'].widget.attrs['placeholder'] = 'Confirm Password'
        self.fields['password2'].label = ''
        self.fields['password2'].help_text = 'Enter the same password for confirmation.'

    def clean_password1(self):
        password1 = self.cleaned_data.get("password1")
        if password1 and len(password1) < 6:
            raise forms.ValidationError("Password must be at least 6 characters long.")
        return password1

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("The two password fields didn't match.")
        
        return password2

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if not username:
            raise forms.ValidationError("Username is required.")
        
        # Check for valid characters
        if not re.match(r'^[a-zA-Z0-9@.+\-_]+$', username):
            raise forms.ValidationError("Username can only contain letters, digits and @/./+/-/_ characters.")
        
        # Check if username already exists
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("A user with this username already exists.")
        
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and User.objects.filter(email=email).exists():
            raise forms.ValidationError("A user with this email already exists.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user

class LocationForm(forms.ModelForm):
    class Meta:
        model = Location
        fields = ['address', 'address_2', 'city', 'state', 'lga']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['lga'].queryset = LGA.objects.none()
        
        if 'state' in self.data:
            try:
                state_id = int(self.data.get('state'))
                self.fields['lga'].queryset = LGA.objects.filter(state_id=state_id)
            except (ValueError, TypeError):
                pass
        elif self.instance and hasattr(self.instance, 'pk') and self.instance.pk and self.instance.state:
            self.fields['lga'].queryset = self.instance.state.lgas.all()

class UserUpdateForm(forms.ModelForm):
    email = forms.EmailField()

    class Meta:
        model = User
        fields = ['last_name', 'first_name', 'username', 'email']

class ProfileUpdateForm(forms.ModelForm):
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    remove_photo = forms.BooleanField(
        required=False,
        widget=forms.HiddenInput(),
        initial=False
    )
    
    class Meta:
        model = Profile
        fields = ['first_name', 'last_name', 'phone_number', 'photo', 'bio', 'remove_photo']
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'photo': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['photo'].required = False
        self.fields['phone_number'].widget.attrs.update({'class': 'form-control'})
    
    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('remove_photo'):
            # Clear the photo field and mark existing file for deletion
            cleaned_data['photo'] = None
            if self.instance.photo:
                self.instance.photo.delete(save=False)
        return cleaned_data
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        if self.cleaned_data.get('remove_photo'):
            instance.photo = None
        
        if commit:
            instance.save()
        return instance

class BusinessVerificationForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = [
            'business_name', 'business_registration_number', 'business_type',
            'business_description', 'business_website', 'business_email', 
            'business_phone', 'business_address_visible'
        ]
        widgets = {
            'business_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter your business name'
            }),
            'business_registration_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter registration number (optional)'
            }),
            'business_type': forms.Select(attrs={'class': 'form-select'}),
            'business_description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Brief description of your business'
            }),
            'business_website': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://your-website.com'
            }),
            'business_email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'business@example.com'
            }),
            'business_phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+234 xxx xxx xxxx'
            }),
            'business_address_visible': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['business_name'].required = True
        self.fields['business_email'].required = True
        self.fields['business_phone'].required = True
        self.fields['business_description'].required = True

class BusinessDocumentForm(forms.ModelForm):
    class Meta:
        model = BusinessVerificationDocument
        fields = ['document_type', 'document', 'description']
        widgets = {
            'document_type': forms.Select(attrs={'class': 'form-select'}),
            'document': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.jpg,.jpeg,.png,.doc,.docx'
            }),
            'description': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Brief description of this document'
            }),
        }
