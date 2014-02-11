import logging

from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext_lazy as _

from widgets import VaccinationWidget, MyDateWidget

# From http://www.djangosnippets.org/snippets/1342/
# To be able to put a datetime field into a hidden
class DateTimeWithUsecsField(forms.DateTimeField):
    def clean(self, value):
        if value and '.' in value: 
            value, usecs = value.rsplit('.', 1) # rsplit in case '.' is used elsewhere
            usecs += '0'*(6-len(usecs)) # right pad with zeros if necessary
            try:
                usecs = int(usecs) 
            except ValueError: 
                raise ValidationError('Microseconds must be an integer') 
        else: 
            usecs = 0 
        cleaned_value = super(DateTimeWithUsecsField, self).clean(value)
        if cleaned_value:
            cleaned_value = cleaned_value.replace(microsecond=usecs)
        return cleaned_value


class MyDateField(forms.DateField):
  '''A DateField with MyDateWidget as the widget'''
  def __init__(self, input_formats=None, *args, **kwargs):
    kwargs['widget'] = MyDateWidget
    super(MyDateField, self).__init__(*args, **kwargs)


class VaccinationField(forms.MultiValueField):
  def __init__(self, doses, *args, **kwargs):
    self.doses = doses
    fieldslist = [MyDateField(label=_("dose %d" % idx), required = False)
                  for idx in range(doses)]
    fields=tuple(fieldslist)
    widgets = VaccinationWidget(doses)
    super(VaccinationField, self).__init__(fields, widget=widgets,
                                       *args, **kwargs)

  def compress(self, data_list):
    # Don't join data_list, just pass it out
    # VaccinationProperty does compression and decompression.

    # Always pass out a list of the right length
    if not isinstance(data_list, list) or len(data_list) != self.doses:
      data_list = [None for dummy in range(self.doses)]
#    logging.info("compress %s" % data_list)

    return data_list
