import logging

from django.forms import TextInput
from django.forms.widgets import RadioInput, MultiWidget
from django.utils.encoding import StrAndUnicode, force_unicode
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _

import models

class RadioFieldRendererNoList(StrAndUnicode):
    """
    An object used by RadioSelect to enable customization of radio widgets.

    Based on django.forms.widgets.RadioFieldRenderer, with mods to 'render'.
    """

    def __init__(self, name, value, attrs, choices):
        self.name, self.value, self.attrs = name, value, attrs
        self.choices = choices

    def __iter__(self):
        for i, choice in enumerate(self.choices):
            yield RadioInput(self.name, self.value, self.attrs.copy(), choice, i)

    def __getitem__(self, idx):
        choice = self.choices[idx] # Let the IndexError propogate
        return RadioInput(self.name, self.value, self.attrs.copy(), choice, idx)

    def __unicode__(self):
        return self.render()

    def render(self):
        """Outputs <input> elements without <ul> or <li> for radio fields."""
        return mark_safe(u'%s' % u'\n'.join([u'%s\n'
                % force_unicode(w) for w in self]))


class TextInputWithLabel(TextInput):
  '''A TextInput that renders with given labeltext.

  NOTE(dan): It is a hack to put the label in the widget instead of the
  field, but Django only puts labels on fields if you run as_p(), which
  isn't running on this widget.  I don't understand Django.
  '''
  def __init__(self, labeltext, attrs=None):
    if attrs is not None:
      self.attrs = attrs.copy()
    else:
      self.attrs = {}
    # Any input with 'datefield' will have a jquery datepicker attached
    self.attrs['class'] = 'datefield'
    self.labeltext = labeltext

  def render(self, name, value, attrs=None):
    out = super(TextInputWithLabel, self).render(name, value, attrs=attrs)
    attrs = self.build_attrs(extra_attrs = attrs)
    return (u'<label for="%s">%s %s</label>'
            % (self.id_for_label(attrs['id']), self.labeltext, unicode(out)))


class VaccinationWidget(MultiWidget):
  """
  A widget that has a list of dates.
  """
  def __init__(self, doses, attrs=None):
    widgets = tuple([TextInputWithLabel(_("dose %d:" % (dose+1)))
                     for dose in range(doses)])
    super(VaccinationWidget, self).__init__(widgets, attrs=attrs)

  def decompress(self, value):
    # Don't decompress, pass out a list with the same number of elements as
    # widgets in __init__.
    if value and isinstance(value, models.Vaccination):
      value = value.dates
    elif not value:
      value = ["", ""]
    else:
      # Erk?
      logging.info("VaccinationWidget.decompress unknown value '%s' type %s"
                   % (value, type(value)))
    return value

  def format_output(self, rendered_widgets):
#    logging.info("format_output %s" % rendered_widgets)
    return u'\n'.join(rendered_widgets)


class MyDateWidget(TextInput):
  def __init__(self, attrs=None):
    # Overwrite class attribute
    if not attrs: attrs = {}
    # Any input with 'datefield' will have a jquery datepicker attached
    attrs['class'] = 'datefield'
    super(MyDateWidget, self).__init__(attrs=attrs)
