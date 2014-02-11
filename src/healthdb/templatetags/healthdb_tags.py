# django dependencies
from django.template import Library

# local imports

register = Library()

@register.inclusion_tag('patient_info.html')
def show_patient_info(patient):
  return { 'patient' : patient }

@register.inclusion_tag('visit_stat_row.html')
def show_visit_stat_row(stat_name, measured, stat):
  return {'stat_name': stat_name,
          'measured' : measured,
          'stat' : stat
         }

@register.inclusion_tag('visit_stat_table.html')
def show_visit_stat_table(visit, visit_stats):
  return {'visit': visit, 'visit_stats': visit_stats }

@register.inclusion_tag('visit_info.html')
def show_visit_info(visit):
  return { 'visit' : visit }

@register.inclusion_tag('zscore_and_percentile.html')
def show_zandp_indicator(zandp):
  return { 'zandp' : zandp }

@register.inclusion_tag('compact_zscore_and_percentile.html')
def show_compact_zandp(zandp):
  return { 'zandp' : zandp }

@register.inclusion_tag('zscore.html')
def show_zscore(zandp):
  return { 'zandp' : zandp }

@register.inclusion_tag('percentile.html')
def show_percentile(zandp):
  return { 'zandp' : zandp }

@register.inclusion_tag('_vaccinations.html')
def show_vaccinations(vaccinations):
  return { 'vaccinations' : vaccinations }

@register.inclusion_tag('years_months_days.html')
def show_years_months_days(age_in_days):
  months = 0
  years = 0
  if age_in_days > 92:
    months = int(age_in_days / 30.4)
    if months > 12:
      years = months / 12
      months = months % 12
  leftover_days = age_in_days - (years * 365 + int(months * 30.4))
  return { 'years': years, 'months': months, 'leftover_days': leftover_days,
           'age_in_days': age_in_days }
