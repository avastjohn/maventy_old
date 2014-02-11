''' Controller Code '''

# Python imports
import logging

# AppEngine imports
from google.appengine.runtime import DeadlineExceededError
from google.appengine.runtime.apiproxy_errors import CapabilityDisabledError


# Django imports
from django.http import HttpResponse, HttpResponseRedirect, Http404
from django.contrib.auth.decorators import login_required

# GAE patch imports
from ragendja.template import render_to_response
from appenginepatcher import on_production_server

# Local imports
import models
import reports
from forms import PatientForm, VisitForm, ContactForm, PatientSearchForm, ConfirmationForm, CalculatorForm, ReportsForm
import mailer

from search.views import show_search_results_from_results, query_param_search

def org_required(func):
  '''Decorator that requires a user to have an organization.

  This requires a user object, so it should always be used after login_required:

  @login_required
  @org_required
  def view_func(request):
    ...
  '''
  def wrap(request, orgStr, *args, **kwargs):
#    logging.info("In org_required wrap, orgStr '%s' isNone %s user.orgStr %s"
#                 % (orgStr, orgStr is None, request.user.organization))
    if not request.user.organization:
      return HttpResponseRedirect('/org-required')
    if not request.user.organization == orgStr:
      return HttpResponseRedirect('/org-must-match')
    if not models.organization_exists(orgStr):
      raise Http404
    return func(request, orgStr, *args, **kwargs)
  return wrap

def respond(request, template, params=None):
  """Helper to render a response, passing standard stuff to the response.

  Args:
    request: The request object.
    template: The template name
    params: A dict giving the template parameters; modified in-place.

  Returns:
    Whatever render_to_response(template, params) returns.

  Raises:
    Whatever render_to_response(template, params) raises.
  """
  if params is None:
    params = {}
  params['is_dev'] = not on_production_server
  try:
    return render_to_response(request, template, params)
  except DeadlineExceededError:
    logging.exception('DeadlineExceededError')
    return HttpResponse('DeadlineExceededError', status=503)
  except CapabilityDisabledError, err:
    logging.exception('CapabilityDisabledError: %s', err)
    return HttpResponse('Undergoing maintenance. '
                        'Please try again in a while. ' + str(err),
                        status=503)
  except MemoryError:
    logging.exception('MemoryError')
    return HttpResponse('MemoryError', status=503)
  except AssertionError:
    logging.exception('AssertionError')
    return HttpResponse('AssertionError')


def index(request):
  return respond(request, 'index.html', {})

@login_required
def database_index(request):
  orgStr = request.user.organization
  def view_func(request, orgStr):
    return respond(request, 'database_index.html',
                   {'search_form': PatientSearchForm(request.GET),
                    'patient_count': models.Patient.get_count(),
                    'visit_count': models.Visit.get_count(),
                    'orgStr': orgStr})
  # NOTE(dan): Use org_required here instead of as a decorator because we have
  # to set orgStr from request.user.organization instead of the URL
  return org_required(view_func)(request, orgStr)



def _store_new_patient(patientForm, orgStr, request_user):
  """Store new patient from patientForm. Returns patient, or None upon error."""
  patient = None
  # store the patient
  try:
    # TODO(dan): Should assign_short_string .. put() in a transaction.
    patient = patientForm.save(commit=False)
    # if request_user is not anonymous, save it in created_by_user
    if request_user.username: patient.created_by_user = request_user
    patient.assign_short_string()
    patient.organization = orgStr
    patient.put()
    models.Patient.increment_count()
  except ValueError, err:
    logging.error("_store_new_patient error: " + unicode(err))
    patientForm.errors['__all__'] = unicode(err)
    patient = None
  return patient

# TODO(dan): Don't bother to support a new patient without a visit for now,
# it doesn't seem to be used
#@login_required
#@org_required
#def patient_new(request, orgStr):
#  """Create a new patient."""
#  if request.method != 'POST':
#    patientForm = PatientForm(initial={'organization':orgStr})
#    return respond(request, 'patient_new.html', {'form': patientForm})
#
#  patientForm = PatientForm(request.POST)
#  if not patientForm.is_valid():
#    return respond(request, 'patient_new.html', {'form': patientForm})
#
#  # store the patient
#  patient = _store_new_patient(patientForm, request.user)
#  if not patient:
#    return respond(request, 'patient_new.html', {'form': patientForm})
#
#  # Email us whenever a patient is created.
#  mailer.email_new_patient(patient)
#
#  return HttpResponseRedirect(patient.get_view_url())


@login_required
@org_required
def patient_edit(request, orgStr, patientStr):
  """Edit an existing patient"""
  patient = models.Patient.get_by_short_string(patientStr)
  if not patient: raise Http404

  def render_this(patient, patientForm):
    return respond(request, 'patient_edit.html',
                   {'patient': patient, 'form': patientForm})

  if request.method != 'POST':
    patientForm = PatientForm(instance=patient)
    return render_this(patient, patientForm)

  patientForm = PatientForm(request.POST, instance=patient)
  if not patientForm.is_valid():
    # logging.info('patient_edit: %s' % patientForm.errors)
    return render_this(patient, patientForm)

  # store the patient
  try:
    patient = patientForm.save(commit=False)
    # NOTE(dan): Use user's org, not possibly hacked org from the request.
    patient.organization = request.user.organization
  except ValueError, err:
    patientForm.errors['__all__'] = unicode(err)
    return render_this(patient, patientForm)
  patient.put()

  return HttpResponseRedirect(patient.get_view_url())

# NOTE(dan): @login_required and @org_required are taken care of in the function
# instead of as decorators because we allow a non-logged-in user to see the
# patient they just entered
def patient_view(request, orgStr, patientStr):
  patient = models.Patient.get_by_short_string(patientStr)
  if not patient: raise Http404

  if not ((request.user.is_authenticated()
           and request.user.organization == orgStr)
          or ('patient' in request.session and
              patient == request.session['patient'])):
    # User is not logged in, and patient is not in session
    # so don't allow them to view the patient
    patient = None

  return respond(request, 'patient_view.html', {'patient': patient,
                                                'orgStr': orgStr})
  
@login_required
@org_required  
def patient_delete(request, orgStr, patientStr):
  """ Delete patient and all his/her visits """
  # TODO(edit): Check org is correct or is_admin
  if not (request.user.is_authenticated()
           and request.user.organization == orgStr):
    # User is not logged in, don't allow them to go on with the delete
    return database_index(request)

  patient = models.Patient.get_by_short_string(patientStr)
  if not patient:
    logging.warning("patient_delete: patient %s not found" % patientStr)
    raise Http404
 
  visits = patient.get_visits()

  # Email us the patient and visits to be deleted
  mailer.email_patient_with_visit_deleted(patient, visits)    

  models.Visit.delete_visits(visits)
        
  patient.delete()
  models.Patient.set_count(models.Patient.get_count() - 1)
    
  return database_index(request)

@login_required
@org_required                
def patient_merge(request, orgStr):
  """Will try to merge patients based on identical fields.
     
     The oldest patient record will be kept with the merged visits
     and the other patients and their associated data will be deleted.
  """
  if not (request.user.is_authenticated()
           and request.user.organization == orgStr):
    # User is not logged in, don't allow them to go on with the merge
    return database_index(request)
  
  message = ''
  
  if request.method == 'GET':
    # get list of patient keys to merge
    merge_patients = request.GET.getlist('checked')
    if merge_patients:
      # get patients from datastore using the selected keys
      patients = models.db.get(merge_patients)
      # TODO(edit): add javascript to grey out the 'Merge' button'
      if len(patients) <= 1:
        message = 'Need to select multiple patients in order to be able to merge.'
        return respond(request, 'patient_merge.html', {'message': message})

      # need to check if certain fields are equal
      for ndx in range(len(patients) - 1):
        # return a message if two patients are not equal
        message = models.Patient.merge_compare_patients(patients[ndx], patients[ndx+1])
        if message:
          return respond(request, 'patient_merge.html', {'message': message})

      # keep the patient created earliest
      patient_to_keep = models.Patient.get_earliest_patient(patients)
      
      # then call a transaction to do all the datastore work
      assert patient_to_keep
      
      # get visits to attach to the patient
      mergevisits = models.Patient.get_visits_to_merge(patient_to_keep, patients)
      
      # run the visit merge in a transaction
      models.db.run_in_transaction(models.Patient.merge_visits, patient_to_keep, mergevisits)
      patient_to_keep.set_latest_visit(patient_to_keep.get_latest_visit())
      
      # run the delete in a transaction --> not allowed
      # if this delete fails, we'll have an extra patient and extra visits
      # TODO(edit): email upon this failure?
      # message = models.db.run_in_transaction(models.Patient.merge_delete, patient_to_keep, patients)
      mailer.email_patient_merge(patient_to_keep, patients)
      message = models.Patient.merge_delete(patient_to_keep, patients)
      models.Patient.set_count(models.Patient.get_count() - (len(patients) - 1))

      if message == None:
        message = 'Successful Merge'
      return respond(request, 'patient_merge.html', {'message': message, 'patient': patient_to_keep})

    if len(merge_patients) == 0:
      message = 'Please select some patients to merge'
                           
  return respond(request, 'patient_merge.html', {'message': message})        

def _store_new_visit(patient, visitForm, request_user):
  """Store a new visit from visitForm.  Returns visit, or None upon error."""
  visit = None
  # store the visit
  try:
    visit = visitForm.save(commit=False)
    #logging.info("visit: %s" % visit)
    visit.assign_short_string()
    # NOTE(dan): Use user's org, not possibly hacked org from the request.
    visit.organization = request_user.organization
    # if request_user is not anonymous, save in created_by_user
    if request_user.username: visit.created_by_user = request_user
    visit.put()
    patient.set_latest_visit(latest_visit = visit)
    models.Visit.increment_count()
  except ValueError, err:
    logging.error("_store_visit error: " + unicode(err))
    visitForm.errors['__all__'] = unicode(err)
    visit = None
  return visit

def _store_new_patient_and_new_visit(request, orgStr, patientForm, visitForm):
  # Save the new data
  patient = _store_new_patient(patientForm, orgStr, request.user)
  if not patient:
    return False 
  request.session['patient'] = patient
  # Reinitialize visitForm with the stored patient
  # You can only set parent upon construction, so make a newVisit
  newVisit = models.Visit(parent = patient)
  visitForm = VisitForm(request.POST, instance = newVisit)

  # store the visit
  visit = _store_new_visit(patient, visitForm, request.user)
  if not visit:
    return False
  # Email us upon new patient-with-visit
  mailer.email_new_patient_with_visit(patient, visit)    
  
  return True

@login_required
@org_required
def visit_new(request, orgStr, patientStr):
  """Create a new visit for a patient."""

  patient = models.Patient.get_by_short_string(patientStr)
  if not patient: raise Http404

  # NOTE(dan): orgStr and patient don't change, so they need not be params
  def render_this(visitForm):
    return respond(request, 'visit_new.html',
                   {'form': visitForm, 'patient': patient,
                    'orgStr': orgStr})

  if request.method != 'POST':
    visitForm = VisitForm(initial={'organization':orgStr})
    return render_this(visitForm)

  # You can only set parent upon construction, so make a newVisit
  newVisit = models.Visit(parent=patient)
  visitForm = VisitForm(request.POST, instance=newVisit)
  if not visitForm.is_valid():
    return render_this(visitForm)

  # store the visit
  visit = _store_new_visit(patient, visitForm, request.user)
  if not visit:
    return render_this(visitForm)

  # Email us whenever a visit is created.
  mailer.email_new_visit(visit)

  return HttpResponseRedirect(visit.get_view_url())


@login_required
@org_required
def visit_edit(request, orgStr, patientStr, visitStr):
  """Edit an existing visit"""
  # need at least one "extra" option form, or the javascript breaks
  patient = models.Patient.get_by_short_string(patientStr)
  if not patient: raise Http404
  visit = patient.get_visit_by_short_string(visitStr)
  if not visit: raise Http404

  # NOTE(dan): patient and orgStr don't change, so they need not be params
  def render_this(visit, visitForm):
    return respond(request, 'visit_edit.html',
                   {'visit': visit, 'form': visitForm, 'orgStr': orgStr})

  if request.method != 'POST':
    visitForm = VisitForm(instance=visit)
    return render_this(visit, visitForm)

  visitForm = VisitForm(request.POST, instance=visit)

  if not visitForm.is_valid():
    logging.error('visit_edit: %s' % visitForm.errors)
    return render_this(visit, visitForm)

  # store the visit
  try:
    visit = visitForm.save(commit=False)
    # TODO(dan): Could possibly set up a Django signal to set_latest_visit
    # Don't set latest_visit param because this visit may not be the latest
    patient.set_latest_visit(force = True)
  except ValueError, err:
    visitForm.errors['__all__'] = unicode(err)
    return render_this(visit, visitForm)
  # Clear cached visit stats
  visit.visit_statistics = None
  visit.put()

  return HttpResponseRedirect(visit.get_view_url())

@login_required
@org_required
def visit_view(request, orgStr, patientStr, visitStr):    
  patient = models.Patient.get_by_short_string(patientStr)
  if not patient:
    logging.warning("visit_view: patient %s not found" % patientStr)
    raise Http404
  visit = patient.get_visit_by_short_string(visitStr)
  if not visit:
    logging.warning("visit_view: patient %s visit %s not found" %
                    (patientStr, visitStr))
    raise Http404

  return respond(request, 'visit_view.html',
                 {'patient': patient, 'visit': visit,
                  'orgStr': orgStr})

@login_required
@org_required
def visit_delete(request, orgStr, patientStr, visitStr):   
  """ Delete visit based on patient and visit number """
  if not (request.user.is_authenticated() 
          and request.user.organization == orgStr):
    # User is not logged in, don't allow them to go on with the delete
    return database_index(request)
   
  patient = models.Patient.get_by_short_string(patientStr)
  if not patient:
    logging.warning("visit_delete: patient %s not found" % patientStr)
    raise Http404

  visit = patient.get_visits_by_short_string(visitStr)
  if not visit:
    logging.warning("visit_delete: patient %s visit %s not found" %
                    (patientStr, visitStr))
    raise Http404

  # Email us the patient and visits to be deleted
  mailer.email_visit_deleted(patient, visit)    
  
  models.Visit.delete_visits(visit)
    
  patient.set_latest_visit(patient.get_latest_visit())
    
  return HttpResponseRedirect(patient.get_view_url()) 

def patient_new_with_visit(request, orgStr):
  """Add a new patient and a new visit to the new patient in one screen.

  Note: You can add patients and visits without being logged in, but you will
  only be able to see the last one.
  """
  #logging.info("request.LANGUAGE_CODE: %s" % request.LANGUAGE_CODE)
  #logging.info("request: %s" % request)
  patient_exists = False

  if not models.organization_exists(orgStr):
    raise Http404

  # NOTE(dan): patient doesn't change, so it need not be a param
  def render_this(patient_exists, confirmationForm, patientForm, visitForm):
    return respond(request, 'patient_new_with_visit.html',
                   {'patient_exists': patient_exists,
                    'confirmationform': confirmationForm,
                    'patientform': patientForm,
                    'visitform': visitForm,
                    'orgStr' : orgStr})

  if request.method != 'POST':
    confirmationForm = ConfirmationForm()
    default_country = getattr(request.user, 'default_country', '')
    if default_country:
      patientForm = PatientForm(initial={'organization':orgStr, 'country': default_country})
    else:
      patientForm = PatientForm(initial={'organization':orgStr})
        
    visitForm = VisitForm(initial={'organization':orgStr})
  else:
    confirmationForm = ConfirmationForm(request.POST)
    patientForm = PatientForm(request.POST)
    visitForm = VisitForm(request.POST)

    if patientForm.is_valid() and visitForm.is_valid():
      # First check if patient exists based on name and date of birth
      name = patientForm.cleaned_data['name']
      birth_date = patientForm.cleaned_data['birth_date']
      patient = models.Patient.get_patient_by_name_birthdate(name, birth_date)
      if patient:
        patient_exists = True
        request.session['patient'] = patient
      
      # If patient is new
      if not patient_exists:
        # Need to store both
        if not _store_new_patient_and_new_visit(request, orgStr, patientForm, visitForm):
          return render_this(patient_exists, confirmationForm, patientForm, visitForm)
      # We already went through this once and there is another patient with same name and birthdate
      else:         
        if confirmationForm.is_valid():  
          confirmation_option = confirmationForm.cleaned_data['confirmation_option']
          if confirmation_option == 'addpatientvisit':
            # Need to store both
            if not _store_new_patient_and_new_visit(request, orgStr, patientForm, visitForm):
              return render_this(patient_exists, confirmationForm, patientForm, visitForm)
          else:              
            # Patient is still the same 
            patient = request.session['patient']                       
            # Just add the visit
            newVisit = models.Visit(parent = patient)
            visitForm = VisitForm(request.POST, instance = newVisit)
            visit = _store_new_visit(patient, visitForm, request.user)        
            if not visit:
              return render_this(patient_exists, confirmationForm, patientForm, visitForm)      
        else:
          return render_this(patient_exists, confirmationForm, patientForm, visitForm)        
            
      patient = request.session['patient']
      # Redirect to viewing
      return HttpResponseRedirect(patient.get_view_url())
                
  return render_this(patient_exists, confirmationForm, patientForm, visitForm)


def contact(request):
  if request.method != 'POST':
    contactForm = ContactForm()
  else:
    contactForm = ContactForm(request.POST)
    if contactForm.is_valid():
      contacter = contactForm.cleaned_data['contacter']
      text = contactForm.cleaned_data['contact_text']
      mailer.email_contact_us(contacter, text)

      return HttpResponseRedirect('/thanks')

  return respond(request, 'contact.html', {'contactform': contactForm})

@login_required
@org_required
def patients_search(request, orgStr):
  form = PatientSearchForm(request.GET)

  filters = ()
  if form.is_valid():
    # Show no results if search returns no results
    key_based_on_empty_query = False

    worst_zscore = form.cleaned_data['worst_zscore']
    if worst_zscore:
      try:
        filters += ('latest_visit_worst_zscore_rounded = ', float(worst_zscore))
      except ValueError, dummy:
        # worst_zscore wasn't a float, don't filter
        pass
    sex = form.cleaned_data['sex']
    if sex:
      filters += ('sex = ', sex)
  
    assert request.user.organization
    filters += ('organization = ', request.user.organization)
    
    default_country = getattr(request.user, 'default_country', '')
    if default_country:
      filters += ('country = ', default_country)
    
#    logging.info('filters: %s' % str(filters))

    # force_query=True so even if query is empty, we have results to start with
    results, query = query_param_search(request, models.Patient, 'search_index',
                                    filters=filters, force_query=True)
    name = form.cleaned_data['name']
    birth_date = form.cleaned_data['birth_date']
    
    if not (worst_zscore or sex or query or name or birth_date):
      # no search fields entered, they must be browsing
      results = None
      # Show all results for browsing if search returns no results
      key_based_on_empty_query = True

    if name:
#      logging.info("filter by name=%s" % name)
      results = models.Patient.name_index.search(name,
                                                 previous_query = results)

    if birth_date:
#      logging.info("filter by birth_date=%s" % birth_date)
      results = models.Patient.birth_date_index.search(birth_date,
                                                 previous_query = results)
  

  else:
    # form is invalid
    # TODO(dan): display an error message on the form
    logging.error("form is invalid")
    # results = None will show browse results.  Confusing?
    results = None

#  logging.info("key_based_on_empty_query: %s" % key_based_on_empty_query)
#  logging.info("results before show: %s" % results)
  return show_search_results_from_results(results,
        request, models.Patient,
        'search_index', filters = filters,
        key_based_on_empty_query = key_based_on_empty_query,
        key_based_order = ('-latest_visit_date', '-latest_visit_short_string'),
        search_form_class = PatientSearchForm,
        extra_context = {'orgStr' : orgStr})

# TODO(dan): Doesn't work yet.
# See http://gae-full-text-search.appspot.com/docs/auto-completion-and-word-prefix-search/
#@login_required
#@org_required
#def live_search(request):
#  '''Return results of a gae search.
#  See http://gae-full-text-search.appspot.com/docs/auto-completion-and-word-prefix-search/
#  '''
#  return live_search_results(request, models.Patient, 'search_index',
#        result_item_formatting=
#            lambda patient: {'value':
#              u'<div>Name: %s</div><div>Residence: %s</div><div>Caregiver name: %s</div>' %
#                              (patient.name,
#                               patient.residence,
#                               patient.caregiver_name),
#                          'result': patient.short_string, })

def dev_run_tasks(request):
  import admin
  return admin.run_tasks(request)

@login_required
@org_required
def select_country(request, orgStr):
  country = request.GET.get('country')
  if country:
    request.user.default_country = country
  else:
    request.user.default_country = ''
  request.user.put()

  return HttpResponseRedirect(request.GET.get('next', '/'))

# TODO(dan): Do per-org, or ditch this
#@login_required
#@org_required
#def download_visits_csv(request):
#  # NOTE: This will not scale to too many visits because
#  # of the 30 second page limit.
#
#  # Read visits and patients in bulk
#  logging.info("load visits")
#  patient_cache, visits = models.Visit.get_all_visits(org)
#
#  # Print
#  doc = models.Visit.export_csv_header() + "\n"
#  for visit in visits:
#    doc += visit.export_csv_line(patient_cache.get_patient(visit.parent_key())) + "\n"
#  response = HttpResponse(doc, mimetype='text/csv')
#  response['Content-Disposition'] = 'attachment; filename=visits.csv'
#  return response

def calculator(request):
  visit = None
  visit_stats = None

  if request.method != 'POST':
    calcForm = CalculatorForm()
  else:
    calcForm = CalculatorForm(request.POST)

    if calcForm.is_valid():
      birth_date = calcForm.cleaned_data['birth_date']
      visit_date = calcForm.cleaned_data['visit_date']
      sex = calcForm.cleaned_data['sex']
      weight = calcForm.cleaned_data['weight']
      head_circumference = calcForm.cleaned_data['head_circumference']
      height = calcForm.cleaned_data['height']
      height_position = calcForm.cleaned_data['height_position']

      visit_stats = models.VisitStatistics.get_stats(
                      birth_date, visit_date, sex, weight,
                      head_circumference, height, height_position, False)

      # Make up a visit psuedo-object for visit_stat_table.html
      # To make a real Visit, we'd need a Patient saved in the datastore
      class PsuedoVisit(object):
        def __init__(self, weight, height, head_circumference):
          self.weight = weight
          self.height = height
          self.head_circumference = head_circumference
      visit = PsuedoVisit(weight, height, head_circumference)

  return respond(request, 'calculator.html',
                 { 'calculatorform': calcForm,
                   'visit': visit,
                   'visit_stats'   : visit_stats,
                 })


@login_required
@org_required
def reports_view(request, orgStr, reportType):
  """ Generate reports
  """

  def render_this(reportsForm, reportType):
    return respond(request, 'reports.html',
                   {'orgStr': orgStr,
                    'reportsForm': reportsForm,
                    'reportType': reportType})

  if request.method != 'POST':
    reportsForm = ReportsForm()
  else:
    reportsForm = ReportsForm(request.POST)

    if reportsForm.is_valid():
      reportType = reportsForm.cleaned_data['report_type']
      visit_date_from = reportsForm.cleaned_data['visit_date_from']
      visit_date_to = reportsForm.cleaned_data['visit_date_to']
      residence = reportsForm.cleaned_data['residence']
      show_detail = reportsForm.cleaned_data['show_detail']
      default_country = getattr(request.user, 'default_country', '')

      report = reports.PatientReport(request.user.organization, visit_date_from, visit_date_to, default_country, residence)

      if reportType == 'undernutrition':
        return report_undernutrition(request, orgStr, reportType, reportsForm, report, residence, show_detail)
      elif reportType == 'screening':
        return report_screening(request, orgStr, reportType, reportsForm, report, residence, show_detail)  
      else:
        return render_this(reportsForm, reportType)
                      
  return render_this(reportsForm, reportType)
 
def report_undernutrition(request, orgStr, report_type, reports_form, report, residence, show_detail):
  """ Generate undernutrition report based on zscores.
  
      An undernutrition report counts all children who have zscore of length-or-height-for-age < -2 (stunted),
      zscore of weight-for-age < -2 (underweight), or zscore of weight-for-length-or-height < -2 (wasting).
  """
  def render_this(reportsForm, reportType, report, reportData, residence, showDetail, reportDetailStunted, reportDetailUnderweight, reportDetailWasting):
    return respond(request, 'reports.html',
                   {'orgStr': orgStr,
                    'reportsForm': reportsForm,
                    'reportType': reportType,
                    'report': report,
                    'reportData': reportData,
                    'residence': residence,                   
                    'showDetail': showDetail,
                    'reportStunted': reportDetailStunted,
                    'reportUnderweight': reportDetailUnderweight,
                    'reportWasting': reportDetailWasting})
  reportsForm = reports_form
  showDetail = show_detail
  reportType = report_type
  zscore = -2
  reportData = report.get_undernutrition_data(zscore)
  reportDetailStunted = []
  reportDetailUnderweight = []
  reportDetailWasting = []
        
  if showDetail:
    reportDetailStunted = report.get_undernutrition_detail('stunted', zscore)
    reportDetailUnderweight = report.get_undernutrition_detail('underweight', zscore) 
    reportDetailWasting = report.get_undernutrition_detail('wasting', zscore)
        
  return render_this(reportsForm, reportType, report, reportData, residence, showDetail, reportDetailStunted, reportDetailUnderweight, reportDetailWasting)

  
def report_screening(request, orgStr, report_type, reports_form, report, residence, show_detail):
  """ Generate total visit report in a date range.
  """
  def render_this(reportsForm, reportType, report, reportData, residence, showDetail, reportDetail):
    return respond(request, 'reports.html',
                   {'orgStr': orgStr,
                    'reportsForm': reportsForm,
                    'reportType': reportType,
                    'report': report,
                    'reportData': reportData,
                    'residence': residence,
                    'showDetail': showDetail,
                    'reportDetail': reportDetail})
  reportsForm = reports_form
  showDetail = show_detail
  reportType = report_type
  reportData = report.get_screening_data()
  reportDetail = []
  if showDetail:
    reportDetail = report.get_screening_details()

  return render_this(reportsForm, reportType, report, reportData, residence, showDetail, reportDetail)
