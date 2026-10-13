from django import forms

from cases.forms import StyledFormMixin

from .models import SiteSettings


class SiteSettingsForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = SiteSettings
        exclude = ["updated_by", "updated_at"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["max_upload_mb"].validators.append(_max_upload_validator)
        self._style_fields()


def _max_upload_validator(value):
    if not 1 <= value <= 25:
        raise forms.ValidationError("Choose a value between 1 and 25 MB.")
