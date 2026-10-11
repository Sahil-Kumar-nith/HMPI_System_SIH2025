from django import forms
from .models import Sample

class GroundwaterSampleForm(forms.ModelForm):
    class Meta:
        model = Sample
        fields = '__all__'

class CsvUploadForm(forms.Form):
    csv_file = forms.FileField()

class SampleFilterForm(forms.Form):
    location = forms.ChoiceField(label='Location', required=False)
    start_date = forms.DateField(label='Start Date', required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    end_date = forms.DateField(label='End Date', required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Get unique location names for dropdown choices
        locations = Sample.objects.values_list('location', flat=True).distinct()
        choices = [('', 'All Locations')] + [(loc, loc) for loc in locations]
        self.fields['location'].choices = choices
