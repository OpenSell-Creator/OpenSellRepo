from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import location,Profile


class SignUpForm(UserCreationForm):
    email = forms.EmailField(label="", required=False, widget=forms.TextInput(attrs={'class':'form-control', 'placeholder':'Email Address (Optional)'}))
    first_name = forms.CharField(label="", max_length=100, required=False, widget=forms.TextInput(attrs={'class':'form-control', 'placeholder':'First Name (Optional)'}))
    last_name = forms.CharField(label="", max_length=100, required=False, widget=forms.TextInput(attrs={'class':'form-control', 'placeholder':'Last Name (Optional)'}))

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
        self.fields['password1'].help_text = 'Your password must contain at least 6 characters.'

        self.fields['password2'].widget.attrs['class'] = 'form-control'
        self.fields['password2'].widget.attrs['placeholder'] = 'Confirm Password'
        self.fields['password2'].label = ''
        self.fields['password2'].help_text = 'Enter the same password as before, for verification.'

    def clean_password1(self):
        password1 = self.cleaned_data.get("password1")
        if len(password1) < 6:
            raise forms.ValidationError("Password must be at least 6 characters long.")
        return password1
    
class LocationForm(forms.ModelForm):

    address = forms.CharField(required=True)
    class Meta:
        model = location
        fields = {'address', 'address_2', 'state', 'district'}
        
class UserUpdateForm(forms.ModelForm):
    email = forms.EmailField()

    class Meta:
        model = User
        fields = ['username', 'email']

class ProfileUpdateForm(forms.ModelForm):
    remove_photo = forms.BooleanField(
        required=False,
        widget=forms.HiddenInput(),
        initial=False
    )

    class Meta:
        model = Profile
        fields = ['phone_number', 'photo', 'bio', 'remove_photo']  # Removed location
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
        