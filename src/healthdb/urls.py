'''URL mappings for the healthdb package.'''

# NOTE: Must import *, since Django looks for things here, e.g. handler500.
from django.conf.urls.defaults import *

urlpatterns = patterns(
    'healthdb.views',

    (r'^$', 'index'),

    (r'^database$', 'database_index'),

    (r'^contact$', 'contact'),
    
    (r'^dev/run-tasks$', 'dev_run_tasks'),

# TODO(dan): live-search works, autocomplete doesn't
#     (r'^patients/live-search$', 'live_search'),

    (r'^(?P<orgStr>[a-z_0-9]+)/patients/new-with-visit1$',
       'patient_new_with_visit'),
                       
    (r'^(?P<orgStr>[a-z_0-9]+)/patient/delete/(?P<patientStr>[a-zA-Z0-9]+)$', 'patient_delete'),
    
    (r'^(?P<orgStr>[a-z_0-9]+)/visit/delete/(?P<patientStr>[a-zA-Z0-9]+)/visit/(?P<visitStr>[a-zA-Z0-9]+)$', 'visit_delete'),
    
    (r'^(?P<orgStr>[a-z_0-9]+)/patient/merge$', 'patient_merge'),
    
    (r'^(?P<orgStr>[a-z_0-9]+)/reports/(?P<reportType>[a-z]+)$', 'reports_view'),

    
# TODO(dan): Don't bother to support a new patient without a visit for now,
# it doesn't seem to be used
#    (r'^(?P<orgStr>[a-zA-Z0-9]+)/patients/new$',
#       'patient_new'),

    (r'^(?P<orgStr>[a-z_0-9]+)/patients/search$',
       'patients_search'),

    (r'^(?P<orgStr>[a-z_0-9]+)/patients/(?P<patientStr>[a-zA-Z0-9]{6,})$',
       'patient_view'),

    (r'^(?P<orgStr>[a-z_0-9]+)/patients/(?P<patientStr>[a-zA-Z0-9]+)/edit$',
       'patient_edit'),

    (r'^(?P<orgStr>[a-z_0-9]+)/patients/(?P<patientStr>[a-zA-Z0-9]+)/visit/new$',
       'visit_new'),

    (r'^(?P<orgStr>[a-z_0-9]+)/patients/(?P<patientStr>[a-zA-Z0-9]+)/visit/(?P<visitStr>[a-zA-Z0-9]+)/$',
      'visit_view'),

    (r'^(?P<orgStr>[a-z_0-9]+)/patients/(?P<patientStr>[a-zA-Z0-9]+)/visit/(?P<visitStr>[a-zA-Z0-9]+)/edit$',
      'visit_edit'),

# TODO(dan): Redo for per-organization download, or ditch
#    (r'^download-visits$', 'download_visits_csv'),

# NOTE(dan): No country selector anymore
    (r'^(?P<orgStr>[a-z_0-9]+)/select-country', 'select_country'),

    (r'calculator', 'calculator')

    )
