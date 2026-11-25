from django import forms

from .models import Interaction


class InteractionForm(forms.ModelForm):
    class Meta:
        model = Interaction
        fields = ['tipo', 'fecha', 'notas']
        widgets = {
            'fecha': forms.DateTimeInput(
                attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'
            ),
        }
