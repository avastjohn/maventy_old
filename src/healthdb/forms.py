# -*- coding: utf-8 -*-

import datetime

from google.appengine.ext.db import djangoforms
from django import forms
from django.utils.translation import ugettext_lazy as _

#from search.forms import LiveSearchField
import models
import widgets
import fields


class ConfirmationForm(forms.Form):
  # to be used when a new patient already exists in the data store
  confirmation_option = forms.ChoiceField( required = True,
                                          label = "",
                                          choices = [['addvisit', _('Add a new visit to the existing patient?')],
                                                     ['addpatientvisit', _('Add a new patient with a new visit?')]],
                                          widget = forms.widgets.RadioSelect(
                                                   attrs={'class': 'radioselect'},
                                                   renderer = widgets.RadioFieldRendererNoList)
                                         )

def _sex_field():
  '''Return a field with two buttons for male and female.'''
  return forms.ChoiceField(required=True,
                           label = _("Sex"),
           choices = [(models.Patient.MALE, _("Male")),
                      (models.Patient.FEMALE, _("Female"))],
           widget = forms.widgets.RadioSelect(
                      attrs={'class': 'radioselect'},
                      renderer = widgets.RadioFieldRendererNoList))


def _birth_date_field():
  '''Return a field for birth date'''
  return fields.MyDateField(required=True, label = _("Birth date"))
  

class PatientForm(djangoforms.ModelForm):
  # Patient.name (db.StringProperty) must be 500 bytes or less
  # http://code.google.com/appengine/docs/python/datastore/typesandpropertyclasses.html#StringProperty
  name = forms.CharField(required=True, max_length = 500,
                         label = _("Patient Name"))
  sex = _sex_field()
  birth_date = _birth_date_field()
  # Patient.residence (db.StringProperty) must be 500 bytes or less
  # http://code.google.com/appengine/docs/python/datastore/typesandpropertyclasses.html#StringProperty
  residence = forms.CharField(required=False, label = _("Residence (Village)"),
                              max_length = 500)
  country = forms.ChoiceField(required=True, label = _("Country"),
              choices = [(choice, choice)
                         for choice in models.Patient.country.choices])
  # Patient.caregiver_name (db.StringProperty) must be 500 bytes or less
  # http://code.google.com/appengine/docs/python/datastore/typesandpropertyclasses.html#StringProperty
  caregiver_name = forms.CharField(required=False, label = _("Caregiver name"),
                                   max_length = 500)

  # HACK(dan): We ignore this form organization and use the user's organization
  # instead, so org can't be hacked.
  organization = forms.CharField(required=True,
                                 widget = forms.widgets.HiddenInput())

  # Vaccination fields
  polio_vaccinations = fields.VaccinationField(
                           label = _("Polio vaccination dates"),
                           doses = 5,
                           required = False)
  dtc_vaccinations = fields.VaccinationField(
                           label = _("DTC (diphtheria, tetanus, and whooping cough) vaccination dates"),
                           doses = 3,
                           required = False)
  hepb_vaccinations = fields.VaccinationField(
                           label = _("Hepatitis B vaccination dates"),
                           doses = 3,
                           required = False)
  measles_vaccinations = fields.VaccinationField(
                           label = _("Measles vaccination dates"),
                           doses = 3,
                           required = False)
  hib_vaccinations = fields.VaccinationField(
                           label = _("HIB (hemophilus influenzae) vaccination dates"),
                           doses = 2,
                           required = False)
  bcg_vaccinations = fields.VaccinationField(
                           label = _(u"BCG (Bacille Calmette-Guérin) vaccination dates"),
                           doses = 1,
                           required = False)
  vita_vaccinations = fields.VaccinationField(
                           label = _("Vitamin A vaccination dates"),
                           doses = 3,
                           required = False)
  deworming_vaccinations = fields.VaccinationField(
                           label = _("Deworming (mebendazole) vaccination dates"),
                           doses = 1,
                           required = False)

  class Meta:
    model = models.Patient
    exclude = ['created_date', 'last_edited', 'short_string',
               'name_index', 'birth_date_index', 'search_index',
               'latest_visit_date', 'latest_visit_short_string',
               'latest_visit_worst_zscore_rounded', 'created_by_user']

#  def __init__(self, data=None, files=None, auto_id=None, prefix=None,
#               initial=None, error_class=None, label_suffix=None,
#               instance=None):
#    import logging
#    logging.info("data %s files %s auto_id %s prefix %s initial %s error_class %s label_suffix %s instance %s"
#                % (data, files, auto_id, prefix, initial, error_class, label_suffix, instance))
#    super(PatientForm, self).__init__(data, files, auto_id, prefix, initial, error_class, label_suffix, instance)


def _visit_date_field():
  return fields.MyDateField(required=True,
                         # the initial value is not localized properly, so don't
                         # use it for now 
                         # initial=datetime.date.today,
                         label = _("Visit date"))

def _weight_field():
  # min_value is INPUT_MINWEIGHT from WHO's AnthroComputation.cs
  # max_value is INPUT_MAXWEIGHT from WHO's AnthroComputation.cs
  return forms.FloatField(required=True,
                          label = _("Weight (kg)"),
                          min_value = 0.9, max_value = 58)

def _head_circumference_field():
  # min_value is INPUT_MINHC from WHO's AnthroComputation.cs
  # max_value is INPUT_MAXHC from WHO's AnthroComputation.cs
  return forms.FloatField(required=False,
                          label = _("Head circumference (cm) (0-24 months only)"),
                          min_value = 25, max_value = 64)

def _height_field():
  # min_value is INPUT_MINLENGTHORHEIGHT from WHO's AnthroComputation.cs
  # max_value is INPUT_MAXLENGTHORHEIGHT from WHO's AnthroComputation.cs
  return forms.FloatField(required=True,
                            label = _("Length or height (cm)"),
                            min_value = 38, max_value = 150)

def _height_position_field():
  return forms.ChoiceField(required=True,
                           label = _("Height position"),
                           choices=[(models.Visit.STANDING, _("Standing")),
                                    (models.Visit.RECUMBENT, _("Recumbent"))],
                           widget = forms.widgets.RadioSelect(
                                      attrs={'class': 'radioselect'},
                                      renderer = widgets.RadioFieldRendererNoList))


class VisitForm(djangoforms.ModelForm):
  visit_date = _visit_date_field()
  weight = _weight_field()
  head_circumference = _head_circumference_field()
  height = _height_field()
  height_position = _height_position_field()

  # Visit.evaluator_name (db.StringProperty) must be 500 bytes or less
  # http://code.google.com/appengine/docs/python/datastore/typesandpropertyclasses.html#StringProperty
  evaluator_name = forms.CharField(required=False, label = _("Evaluator name"),
                                   max_length = 500)

  # HACK(dan): We ignore this form organization and use the user's organization
  # instead, so org can't be hacked.
  organization = forms.CharField(required=True,
                                 widget = forms.widgets.HiddenInput())

  class Meta:
    model = models.Visit
    exclude = ['created_date', 'last_edited', 'short_string',
               'visit_statistics', 'created_by_user']


class ContactForm(forms.Form):
  contacter = forms.EmailField(required=False, label=_('Your Email (optional)'),
                   widget=forms.widgets.TextInput(attrs={'size': '50'}))
  contact_text = forms.CharField(required=True,
                   widget=forms.widgets.Textarea(attrs=
                        {'rows': '10',
                         'cols': '70',
                         'class': 'defaultText',
                         'title': _('Type a message here')}))

class PatientSearchForm(forms.Form):
#class PatientSearchForm(forms.Form):
  # LiveSearchField doesn't work yet, but see
  # http://gae-full-text-search.appspot.com/docs/auto-completion-and-word-prefix-search/
  # query = LiveSearchField('/patients/live-search')
  name = forms.CharField(required=False, label=_('Name'))
  sex = forms.ChoiceField(required=False, label=_('Sex'),
                   choices = (('', _('Any')),
                              (models.Patient.MALE, _('Male')),
                              (models.Patient.FEMALE, _('Female'))))
  # birth_date is a char field because they can enter a prefix (e.g., "2009-10")
  birth_date = forms.CharField(required=False, label=_('Date of birth (YYYY-MM-DD or YYYY-MM or YYYY)'))
  # HACK(dan): The -3.0 below is linked to Patient.set_latest_visit
  worst_zscore = forms.ChoiceField(required=False, label=_('Worst z-score'),
                   choices = ((None, _('Any')),
                              (models.Patient.BELOW_LOWEST_ZSCORE, _('below -3')),
                              (-3.0, _('-3 to -2')),
                              (-2.0, _('-2 to -1')),
                              (-1.0, _('-1 to 0')),
                              ( 0.0, _('0 to 1')),
                              ( 1.0, _('1 to 2')),
                              ( 2.0, _('2 to 3')),
                              ))
  # From GaeSearchForm
  query = forms.CharField(label=_(
            'Extended Search (name, residence, birth date, caregiver)'),
            required=False)

class CalculatorForm(forms.Form):
  sex = _sex_field()
  birth_date = _birth_date_field()
  visit_date = _visit_date_field()
  weight = _weight_field()
  head_circumference = _head_circumference_field()
  height = _height_field()
  height_position = _height_position_field()

class ReportsForm(forms.Form):
  
  report_type = forms.ChoiceField(required=True, label=_('Report Type'),
                                  choices = ((
                                              ('screening', _('Screening Report')),
                                              ('undernutrition', _('Undernutrition Report'))
                                              )))
  
  visit_date_from = fields.MyDateField(required=True,
                         label = _("Visit Date From"))
  
  visit_date_to = fields.MyDateField(required=True,
                         label = _("Visit Date To"))

  residence = forms.CharField(required=False, label = _("Residence (Village)"),
                              max_length = 500)

  show_detail = forms.BooleanField(required=False,
                                   label=_('Show Report Details?'))