from django import forms
from .models import Message

class MessageForm(forms.ModelForm):
    inquiry_type = forms.ChoiceField(
        choices=[('', 'Select a suggested message')] + Message.SUGGESTIONS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select mb-2'})
    )

    class Meta:
        model = Message
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }