# django dependencies
from django.template import Library

# local imports
register = Library()

@register.inclusion_tag('report_screening.html')
def show_screening_report(report, reportData, residence, showDetail, reportDetail):
  return {'report': report, 'reportData': reportData, 'residence': residence, 'showDetail': showDetail, 'reportDetail': reportDetail }

@register.inclusion_tag('report_undernutrition.html')
def show_undernutrition_report(report, reportData, residence, showDetail, reportStunted, reportUnderweight, reportWasting):
  return {'report': report, 'reportData': reportData, 'residence': residence, 'showDetail': showDetail, 
          'reportStunted': reportStunted, 'reportUnderweight': reportUnderweight, 'reportWasting': reportWasting}  

@register.inclusion_tag('report_undernutrition_detail.html')
def show_undernutrition_detail(reportUndernutrition, detailName):
  return {'reportUndernutrition': reportUndernutrition, 'detailName': detailName}