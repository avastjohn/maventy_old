from django import forms
from django.utils.translation import ugettext_lazy as _

class SearchForm(forms.Form):
    query = forms.CharField(label=_('Find'), required=False)

class LiveSearchField(forms.CharField):
    def __init__(self, src, multiple_values=False, select_first=False,
                 auto_fill=False, must_match=False, match_contains=True,
                 cleanup_via=None, **kwargs):
        attrs = {'src': src}
        classes = []
        if multiple_values:
            classes.append('multiple-values')
        if select_first:
            classes.append('select-first')
        if auto_fill:
            classes.append('auto-fill')
        elif match_contains:
            classes.append('match-contains')
        if must_match:
            classes.append('must-match')
        if classes:
            attrs['class'] = ' '.join(classes)
        self.cleanup_via = cleanup_via
        super(LiveSearchField, self).__init__(
            widget=forms.TextInput(attrs=attrs), **kwargs)

    def clean(self, value):
        if self.cleanup_via and value.lower() == value:
            alternatives = self.cleanup_via.search(value).fetch(7)
            for alternative in alternatives:
                alternative = getattr(alternative,
                                      self.cleanup_via.properties[0])
                if alternative != value and alternative.lower() == value:
                    value = alternative
                    break
        return super(LiveSearchField, self).clean(value)
