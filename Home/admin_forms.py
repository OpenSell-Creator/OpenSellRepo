"""
Forms for the custom Home admin pages (banners and catalog).

Limits are chosen from the model and the site:
  - Banner desktop 1200x200 (6:1) and mobile 800x200 (4:1) come from Banner.help_text.
    Banner.save() converts to WebP at q85, so a 1200x200 file is normally well under
    200 KB. 2 MB is a generous cap that still stops phone-camera originals.
  - Category images are resized to 80x80 by Category.save(), so 2 MB is plenty.
"""
import re

from django import forms
from django.core.files.uploadedfile import UploadedFile
from django.utils.text import slugify

from .models import Banner, Brand, Category, Subcategory

MAX_BANNER_BYTES = 2 * 1024 * 1024
MAX_CATEGORY_IMAGE_BYTES = 2 * 1024 * 1024
HEX_COLOR = re.compile(r'^#[0-9A-Fa-f]{6}$')
DT_FORMAT = '%Y-%m-%dT%H:%M'  # what <input type="datetime-local"> submits


def _check_size(upload, limit, label):
    # Only uploaded files are checked: an unchanged field returns the stored FieldFile.
    if isinstance(upload, UploadedFile) and upload.size > limit:
        mb = limit // (1024 * 1024)
        raise forms.ValidationError(f'{label} is {upload.size / 1048576:.1f} MB. Keep it under {mb} MB.')
    return upload


def _unique_slug(form, name, qs, typed):
    """
    typed slug  -> must be free, otherwise a validation error.
    blank slug  -> slugified name, with -2, -3 ... added until it is free.
    """
    if form.instance.pk:
        qs = qs.exclude(pk=form.instance.pk)
    base = slugify(typed or name)[:100]
    if not base:
        raise forms.ValidationError('Could not build a slug from this name. Type one in.')
    if typed:
        if qs.filter(slug=base).exists():
            raise forms.ValidationError(f'The slug "{base}" is already in use.')
        return base
    candidate, n = base, 2
    while qs.filter(slug=candidate).exists():
        suffix = f'-{n}'
        candidate = base[:100 - len(suffix)] + suffix
        n += 1
    return candidate


# --------------------------------------------------------------------------- banners
class BannerAdminForm(forms.ModelForm):
    start_date = forms.DateTimeField(
        required=False,
        input_formats=[DT_FORMAT, '%Y-%m-%d %H:%M', '%Y-%m-%d'],
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'ox-ctl'}, format=DT_FORMAT),
    )
    end_date = forms.DateTimeField(
        required=False,
        input_formats=[DT_FORMAT, '%Y-%m-%d %H:%M', '%Y-%m-%d'],
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'ox-ctl'}, format=DT_FORMAT),
    )

    class Meta:
        model = Banner
        fields = ['image', 'mobile_image', 'url', 'display_location', 'is_active',
                  'priority', 'background_color', 'start_date', 'end_date']
        widgets = {
            'url': forms.URLInput(attrs={'class': 'ox-ctl', 'placeholder': 'https://opensell.ng/affiliate', 'inputmode': 'url'}),
            'display_location': forms.Select(attrs={'class': 'ox-ctl'}),
            'priority': forms.NumberInput(attrs={'class': 'ox-ctl', 'inputmode': 'numeric'}),
            'background_color': forms.TextInput(attrs={'class': 'ox-ctl', 'placeholder': '#FF5733', 'maxlength': 7, 'autocomplete': 'off'}),
            'is_active': forms.CheckboxInput(),
        }

    def clean_image(self):
        return _check_size(self.cleaned_data.get('image'), MAX_BANNER_BYTES, 'Desktop image')

    def clean_mobile_image(self):
        return _check_size(self.cleaned_data.get('mobile_image'), MAX_BANNER_BYTES, 'Mobile image')

    def clean_url(self):
        url = (self.cleaned_data.get('url') or '').strip()
        if not url.lower().startswith(('http://', 'https://')):
            raise forms.ValidationError('Use a full web address starting with http:// or https://')
        return url

    def clean_background_color(self):
        value = (self.cleaned_data.get('background_color') or '').strip()
        if not value:
            return None
        if not HEX_COLOR.match(value):
            raise forms.ValidationError('Use a hex colour such as #FF5733.')
        return value

    def clean(self):
        data = super().clean()
        start, end = data.get('start_date'), data.get('end_date')
        if start and end and end <= start:
            self.add_error('end_date', 'The end must be after the start.')
        return data


# --------------------------------------------------------------------------- catalog
class _CatalogBase(forms.ModelForm):
    """Name + optional slug. Slug is generated from the name when left blank."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['slug'].required = False
        self.fields['name'].widget.attrs.update({'class': 'ox-ctl', 'autocomplete': 'off'})
        self.fields['slug'].widget.attrs.update({'class': 'ox-ctl', 'autocomplete': 'off', 'placeholder': 'Generated from the name'})

    def _name_taken(self, qs, name):
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        return qs.filter(name__iexact=name).exists()


class CategoryAdminForm(_CatalogBase):
    class Meta:
        model = Category
        fields = ['name', 'slug', 'image']

    def clean_name(self):
        name = (self.cleaned_data.get('name') or '').strip()
        if self._name_taken(Category.objects.all(), name):
            raise forms.ValidationError('A category with this name already exists.')
        return name

    def clean_image(self):
        return _check_size(self.cleaned_data.get('image'), MAX_CATEGORY_IMAGE_BYTES, 'Image')

    def clean(self):
        data = super().clean()
        name = data.get('name')
        if name and not self.errors.get('slug'):
            try:
                data['slug'] = _unique_slug(self, name, Category.objects.all(), (data.get('slug') or '').strip())
            except forms.ValidationError as exc:
                self.add_error('slug', exc)
        return data


class SubcategoryAdminForm(_CatalogBase):
    class Meta:
        model = Subcategory
        fields = ['category', 'name', 'slug']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = Category.objects.order_by('name')
        self.fields['category'].widget.attrs.update({'class': 'ox-ctl'})
        self.fields['category'].empty_label = 'Select category'

    def clean(self):
        data = super().clean()
        category, name = data.get('category'), (data.get('name') or '').strip()
        if category and name:
            siblings = Subcategory.objects.filter(category=category)
            if self._name_taken(siblings, name):
                self.add_error('name', f'"{category.name}" already has a subcategory with this name.')
            elif not self.errors.get('slug'):
                try:
                    data['slug'] = _unique_slug(self, name, siblings, (data.get('slug') or '').strip())
                except forms.ValidationError as exc:
                    self.add_error('slug', exc)
        return data


class BrandAdminForm(_CatalogBase):
    class Meta:
        model = Brand
        fields = ['name', 'slug', 'categories', 'subcategories']
        widgets = {
            'categories': forms.CheckboxSelectMultiple(),
            'subcategories': forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['categories'].queryset = Category.objects.order_by('name')
        # Subcategory.__str__ prints "Category - Name", so join the category once.
        self.fields['subcategories'].queryset = (
            Subcategory.objects.select_related('category').order_by('category__name', 'name')
        )

    def clean_name(self):
        name = (self.cleaned_data.get('name') or '').strip()
        if self._name_taken(Brand.objects.all(), name):
            raise forms.ValidationError('A brand with this name already exists.')
        return name

    def clean(self):
        data = super().clean()
        name = data.get('name')
        if name and not self.errors.get('slug'):
            try:
                data['slug'] = _unique_slug(self, name, Brand.objects.all(), (data.get('slug') or '').strip())
            except forms.ValidationError as exc:
                self.add_error('slug', exc)

        # The listing form offers brands by subcategory, so the two lists must agree.
        cats, subs = data.get('categories'), data.get('subcategories')
        if cats is not None and subs is not None:
            cat_ids = {c.pk for c in cats}
            stray = [str(s) for s in subs if s.category_id not in cat_ids]
            if stray:
                self.add_error(
                    'subcategories',
                    'These subcategories belong to categories you did not tick: ' + ', '.join(stray[:5]) + '.',
                )
        return data
