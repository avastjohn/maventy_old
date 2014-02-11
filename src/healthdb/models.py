# -*- coding: utf-8 -*-
 
''' Schema 

@see http://code.google.com/appengine/docs/python/datastore/typesandpropertyclasses.html
@see http://code.google.com/appengine/docs/python/datastore/propertyclass.html
'''

# Python imports
import logging
import urlparse
from datetime import date

# AppEngine imports
from google.appengine.ext import db

# Django imports
from django.db import models
#from django.db.models.signals import post_save
from django.utils.translation import ugettext_lazy as _

# Local imports
import counter
import util
import search_util
from growthcalc.growthcalc import VisitStatistics
from growthcalc.growthcalc import ZscoreAndPercentileProperty

from search.core import SearchIndexProperty, startswith

def organization_exists(orgStr):
  # TODO(dan): We will want this list in the datastore
  # maventy.org: contact Martin Malachovsky, drm - at - maventy.org
  # RVM: contact Marcela Micelli, miceli.marcela - at - gmail
  return orgStr in ['maventy', 'rvm', 'test']


class Vaccination(object):
  """A class to contain records about a Vaccination given to a patient."""
  def __init__(self, date_list = []):
#    logging.info("__init__ date_list %s id %s" % (date_list, id(date_list)))
    # NOTE(dan): self.dates = date_list is a bug!  date_list persists.
    self.dates = []
    self.dates.extend(date_list)

  def add_date(self, date):
    self.dates.append(date)

  def __str__(self):
    """String for debugging"""
    return "dates %s" % (self.dates)

  def __len__(self):
    return len(self.dates)

  def __cmp__(self, other):
    '''Return -1 if self < other, 0 if self == other, 1 if self > other.'''
    if other is None: return 1
    val = len(self.dates) - len(other.dates)
    if not val:
      # lengths are equal, test members
      for idx in range(len(self.dates)):
        date1 = self.dates[idx]
        date2 = other.dates[idx]
        if not date1 and not date2: val = 0
        elif not date1 and date2: val = -1
        elif date1 and not date2: val = 1
        else:
          tdelta = date1 - date2
          val = tdelta.days
        if val: break 
    return val

class VaccinationProperty(db.Property):
  """A Vaccination property class."""
  data_type = Vaccination

  def get_value_for_datastore(self, model_instance):
    vacc = super(VaccinationProperty, self
                     ).get_value_for_datastore(model_instance)
    if vacc:
      date_list = []
      for date in vacc.dates:
        if date:
          date_list.append((date.year * 10000) + (date.month * 100) + date.day)
        else:
          # We need a string for every entry in date_list to preserve order
          date_list.append("")
      vacc = ':'.join(map(str, date_list))
    return vacc

  def make_value_from_datastore(self, value):
    vacc = None
    # If there's a value and it's not all :s
    if value and value.count(":") < len(value):
      vals = value.split(':')
      vacc = Vaccination()
      if len(vals) > 0:
        for datenum in vals:
          if datenum:
            datenum = int(datenum)
            vacc.add_date(date(year=datenum / 10000,
                             month=(datenum / 100) % 100,
                             day=datenum % 100))
          else:
            vacc.add_date(None)
      assert len(vacc) == len(vals), 'vacc %d vals %d' % (len(vacc), len(vals))
    return vacc

  def validate(self, value):
    if value is not None and not isinstance(value, Vaccination):
        raise db.BadValueError('Property %s must be convertible '
                            'to a Vaccination instance (%s)' %
                            (self.name, value))
    return super(VaccinationProperty, self).validate(value)

  def empty(self, value):
      return not value


class Patient(db.Model):
  MALE = 'MALE'
  FEMALE = 'FEMALE'

  # HACK(dan): BELOW_LOWEST_ZSCORE indicates any zscore below -3.
  BELOW_LOWEST_ZSCORE = -4.0

  # properties ignored when comparing patient attributes
  COMPARE_IGNORE_PROPS = [u'search_index', u'short_string', u'last_edited',
                          u'created_date', u'latest_visit_worst_zscore_rounded',
                          u'latest_visit_date', u'created_by_user', u'latest_visit_short_string',
                          u'short_string', u'name_index', u'birth_date_index',
                          u'latest_visit_date',
                          u'caregiver_name' ] 
  
  # Date created in this DB
  created_date = db.DateTimeProperty(required=True, auto_now_add=True)
  # Last edited in this DB
  last_edited = db.DateTimeProperty(required=True, auto_now=True)

  # user who created the visit
  created_by_user = db.ReferenceProperty(required=False)

  # Easy way to refer to a patient
  # TODO(dan): Make short_string required=True.  It's a little tricky.
  short_string = db.StringProperty(required=False)

  name = db.StringProperty(required=True)
  sex = db.StringProperty(required=True, choices = [MALE, FEMALE])
  birth_date = db.DateProperty(required=True)

  residence = db.StringProperty(required=False)
  organization = db.StringProperty(required = True)
  # TODO(dan): How to properly translate country names?  Do we need to?
  country = db.StringProperty(required = True,
                              choices = ['India', 'Madagascar', 'Uganda', 'other'])
  caregiver_name = db.StringProperty(required=False)

  # We want to restrict by several fields using self-merge-joins, so we can't
  # use relation indexes for the individual fields name and birth_date
  name_index = SearchIndexProperty(('name'),
                                      indexer = startswith,
                                      splitter = search_util.splitter,
                                      relation_index = False)

  birth_date_index = SearchIndexProperty(('birth_date'),
                                      indexer = startswith,
                                      splitter = search_util.splitter,
                                      relation_index = False)

  # search_index has all the fields mixed together
  search_index = SearchIndexProperty(('name', 'residence', 'birth_date',
                                      'caregiver_name'),
                                      indexer = startswith,
                                      splitter = search_util.splitter,
                                      # We want to restrict by several fields
                                      # using self-merge-joins, so we can't use
                                      # a relation index
                                      relation_index = False)

  # Cached from latest visit, to sort by
  latest_visit_date = db.DateProperty(required=False)
  
  # Added to make the visit unique
  latest_visit_short_string = db.StringProperty(required=False)
  
  # Cached from latest_visit_worst_zscore, to filter by
  latest_visit_worst_zscore_rounded = db.FloatProperty(required=False)

  # Vaccination records
  # TODO(dan): Could do a list property of vaccinations instead.
  # Might be cleaner.

  # polio
  polio_vaccinations = VaccinationProperty(required=False)

  # diphtérie, Tétanos, Coqueluche (French: diphtheria, tetanus, and whooping cough)
  dtc_vaccinations = VaccinationProperty(required=False)

  # hepatitis
  hepb_vaccinations = VaccinationProperty(required=False)

  measles_vaccinations = VaccinationProperty(required=False)

  # hib is hemophilus influenzae
  hib_vaccinations = VaccinationProperty(required = False)

  # http://en.wikipedia.org/wiki/Bacillus_Calmette-Gu%C3%A9rin against tuberculosis
  bcg_vaccinations = VaccinationProperty(required = False)

  # vitamin A
  vita_vaccinations = VaccinationProperty(required = False)

  # deworming: mebendazole
  deworming_vaccinations = VaccinationProperty(required = False)

  @property
  def id(self):
    return self.key().id()

  def __str__(self):
    return "<Patient id=%s, name=%s, short_string=%s>" % (
      self.id, self.name, self.short_string)

  @models.permalink
  def get_view_url(self):
    return ('healthdb.views.patient_view', (),
            {'patientStr': self.short_string,
             'orgStr' : self.organization})

  @models.permalink
  def get_edit_url(self):
    return ('healthdb.views.patient_edit', (),
            {'patientStr': self.short_string,
             'orgStr' : self.organization})

  @models.permalink
  def get_new_visit_url(self):
    return ('healthdb.views.visit_new', (),
            {'patientStr': self.short_string,
             'orgStr' : self.organization})

  def get_view_fullurl(self):
    return urlparse.urljoin(util.get_domain(), self.get_view_url())
    
  @staticmethod
  def get_by_short_string(short_string):
    return Patient.gql('WHERE short_string = :1', short_string).get()

  @staticmethod  
  def get_patient_by_name_birthdate(name, birth_date):   
    ''' Get a patient with the given name and birth_date
 
        If there is more than one, get the most recently created.
        If there is none, return None.
    '''   
    return Patient.gql('WHERE name = :1 and birth_date = :2 order by created_date desc', name, birth_date).get()

  @staticmethod
  def merge_compare_patients(patient_a, patient_b):
    '''Compare two patients on properties not in Patient.COMPARE_IGNORE_PROPS

       If all fields are equal, it returns an empty message.
       If any field is not equal, it will return a message with the inequality.
    '''
    if type(patient_a) != type(patient_b):
      return "Internal error"
      # TODO(dan): Should check type(patient_a) == Patient

    for prop in Patient.properties():
      if prop not in Patient.COMPARE_IGNORE_PROPS:
        attr_a = getattr(patient_a, prop)
        attr_b = getattr(patient_b, prop)
        if prop == 'name':
          # Make 'name' comparison case-insensitive
          attr_a = attr_a.lower()
          attr_b = attr_b.lower()  
        if attr_a != attr_b:
          return prop + ": " + str(attr_a) + " is not equal to " + str(attr_b)
       
    return ''
  
  @staticmethod
  def get_earliest_patient(patients):
    """ This routine will return the earliest created patient from the given list
  
    """
    earliest_patient = None
  
    # loop and compare dates to find the earliest created patient
    for patient in patients:
      if not earliest_patient or (earliest_patient.created_date > patient.created_date):
        earliest_patient = patient
    return earliest_patient

  @staticmethod
  def get_visits_to_merge(patient_to_keep, patients):
    """ This function returns the visits from all patients in "patients" that
        are not in patient_to_keep.
    
    """
    temp_visits = []
    for patient_to_merge in patients:
      if patient_to_merge.key() != patient_to_keep.key():
        # retrieve visits to merge
        temp_visits.extend(patient_to_merge.get_visits())
    
    # mergevisits is temp_visits, but without old patients as parents
    mergevisits = [visit.copydata() for visit in temp_visits]             
    
    return mergevisits

  @staticmethod
  def merge_visits(patient_to_keep, mergevisits):  
    """ This function will merge visits
  
    """
    for temp in mergevisits:
      Visit.get_visit_statistics(temp)        
      temp.copy_to_patient(patient_to_keep)
            
    # set the latest visit
    # did not allow me to nest these two functions
    # patient_to_keep.set_latest_visit(patient_to_keep.get_latest_visit())
    # Error:    'Only ancestor queries are allowed inside a transaction.')
    # BadRequestError: Only ancestor queries are allowed inside a transaction.
           
  @staticmethod
  def merge_delete(patient_to_keep, patients):
    """ Delete visits from patients in "patients" except for patient that is patient_to_keep """
    message = ""
    for deletepatient in patients:
      if deletepatient.key() != patient_to_keep.key():
        # first find visits to delete
        deletevisits = db.Query(Visit).ancestor(deletepatient)
        if deletevisits:
          # Not allowed to call Visit.delete_visits(deletevisits) because this function
          # will decrement the count and this is not needed in the merge
          for deletevisit in deletevisits:
            deletevisit.delete()
            deletevisit.delete_statistics()
            
        # once the visits are merged, delete the patient
        message = deletepatient.delete()
    return message

  @staticmethod
  def get_count():
    return counter.get_count('Patient')

  @staticmethod
  def increment_count():
    return counter.increment('Patient')

  @staticmethod
  def set_count(count):
    return counter.set_value('Patient', count)
   
  def assign_short_string(self):
    assert self.short_string is None, "Tried to assign short_string twice"
    while not self.short_string:
      # 1 / (31^6) = 1e-9 is the probability two strings collide
      # in an empty space
      # TODO(dan): This should be in a transaction
      astr = util.random_string(6)
      if not Patient.get_by_short_string(astr):
        self.short_string = astr
        #logging.info('assigned short string: %s' % self.short_string)
        # There are funny race conditions if we don't save
        # Do we need the whole "sharded counter" business?
        # self.save

  def get_visits(self):
    return list(Visit.gql('WHERE ANCESTOR IS :1', self))

  def get_ordered_visits(self):
    return list(Visit.gql('WHERE ANCESTOR IS :1 ORDER BY created_date ASC', self))

  def get_latest_visit(self):
    if not hasattr(self, '_latest_visit'):
      self._latest_visit = Visit.gql(
        'WHERE ANCESTOR IS :1 ORDER BY created_date desc, short_string',
        self).get()
    return self._latest_visit

  def get_num_visits(self):
    query = db.Query(Visit)
    query.ancestor(self)
    return query.count()

  def get_visit_by_short_string(self, visitStr):
    result = list(Visit.gql('WHERE ANCESTOR IS :1 and short_string = :2',
                            self, visitStr))
    assert len(result) < 2
    if len(result) == 1:
      result = result[0]
    else:
      result = None
    return result

  def get_visits_by_short_string(self, visitStr):
    result = list(Visit.gql('WHERE ANCESTOR IS :1 and short_string = :2',
                            self, visitStr))
    return result

  def has_visits(self):
    return self.get_num_visits() > 0

  def set_latest_visit(self, latest_visit = None, force = False, put = True):
    '''Set latest visit cache.

    latest_visit: if the caller knows the latest visit, it can be given,
                  otherwise it is queried
    force: recalculate even if the cache is the same
    put: if False, don't put, so caller can do bulk puts.

    Could throw a TypeError if there is no visit with a numeric zscore.
    '''
    logging.info("Recalculate latest_visit_cache for %s" % self.short_string)
    needs_put = False
    if latest_visit is None:
      latest_visit = self.get_latest_visit()
    if latest_visit:
      if force:
        self.latest_visit_date = latest_visit.visit_date
        self.latest_visit_short_string = latest_visit.short_string
        # TODO(dan): This throws a TypeError if get_worst_zscore is not
        # a float.  Do all clients deal with that?
        self.latest_visit_worst_zscore_rounded = util.bucket_zscore(
          latest_visit.get_visit_statistics().get_worst_zscore())
        # Bound at the bottom for sorting and filtering
        # HACK(dan): This -3 is linked to PatientSearchForm
        if self.latest_visit_worst_zscore_rounded < -3:
          self.latest_visit_worst_zscore_rounded = Patient.BELOW_LOWEST_ZSCORE
#        logging.info("rounded %s" % self.latest_visit_worst_zscore_rounded)

        needs_put = True
        if put:
          self.put()
#        logging.info("Needs put: %s" % self.short_string)
    return needs_put
    
class PatientCache():
  """A collection of patient objects read from the given keys"""
  def __init__(self, patient_keys):
    self._cache = {}
    self.load_patients(patient_keys)

  def load_patients(self, patient_keys):
    '''Load more patients into the cache.'''
    logging.info("load PatientCache with %d keys" % len(patient_keys))
    keys = [key for key in patient_keys if key not in self._cache]
    num = 0
    # get patients in chunks so we don't get a 500 error
    CHUNK_SIZE = 100
    while keys:
      some_keys = keys[0:CHUNK_SIZE]
      del keys[0:CHUNK_SIZE]

      for patient in db.get(some_keys):
        num += 1
        self._cache[patient.key()] = patient
      logging.info("Read %d patients" % num)

  def get_patient(self, patient_key):
    return self._cache[patient_key]


class Visit(db.Model):
  STANDING = 'STANDING'
  RECUMBENT = 'RECUMBENT'
  UNKNOWN = 'UNKNOWN'

  # parent is Patient

  # Date created in this DB
  created_date = db.DateTimeProperty(required=True, auto_now_add=True)
  # Last edited in this DB
  last_edited = db.DateTimeProperty(required=True, auto_now=True)

  # user who created the visit
  created_by_user = db.ReferenceProperty(required=False)

  evaluator_name = db.StringProperty(required=False)

  short_string = db.StringProperty(required=False)

  # Unfortunately, due to the way we init visit with parent Patient,
  # we need to specify a default visit_date.  On the bright side,
  # form validation can still catch an unset property
  visit_date = db.DateProperty(required=True, default = date.today())
  weight = db.FloatProperty(required=True, default = 0.0)
  head_circumference = db.FloatProperty()
  height = db.FloatProperty(required=True, default = 0.0)
  # Unfortunately, due to the way we init visit with parent Patient,
  # we need to specify a default height_position.  On the bright side,
  # form validation can still catch an unset property
  height_position = db.StringProperty(required=True,
                                      choices=[STANDING, RECUMBENT],
                                      default = STANDING)
  visit_statistics = db.ReferenceProperty(reference_class = VisitStatistics,
                                          required = False, default = None)
  # 'organization' comes from the parent Patient
  # We duplicate it on Visit in order to query against it
  # TODO(dan): Change to required=True
  organization = db.StringProperty(required = False)

  # Notes about the visit
  notes = db.TextProperty(required=False, verbose_name = _('Visit notes'))

  @property
  def id(self):
    return self.key().id()

  def __str__(self):
    return ("<Visit id=, parent=%s, created_date=%s, last_edited=%s,"
            " short_string=%s, visit_date=%s, weight=%s, head_circumference=%s,"
            " height=%s, height_position=%s>" % (
      #self.id,
      self.parent(), self.created_date, self.last_edited,
      self.short_string, self.visit_date, self.weight, self.head_circumference,
      self.height, self.height_position))

  def assign_short_string(self):
    assert self.short_string is None, "Tried to assign short_string twice"
    while not self.short_string:
      # 1 / (31^6) = 1e-9 is the probability two strings collide
      # in an empty space
      astr = util.random_string(6)
      if not Visit.get_by_short_string(astr):
        self.short_string = astr

  @staticmethod
  def get_by_short_string(short_string):
    return Visit.gql('WHERE short_string = :1', short_string).get()

  def copy_to_patient(self, patient):
    """ Create visit like this and attach it to patient """
    newVisit = Visit(parent=patient)
    for prop in self.properties():
      # copy from self to newVisit
      setattr(newVisit, prop, getattr(self, prop)) 
    # Could not call put_visit(). The error says 'Nested transactions are not supported' when 
    # the code calls Visit.increment_count() 
    #newVisit.assign_short_string()
    newVisit.put()    

  def copydata(self):
    """ Create visit like this without a parent key """
    newVisit = Visit()
    for prop in self.properties():
      if prop == 'created_by_user':
        setattr(newVisit, prop, None)
      else:
        # copy from self to newVisit
        setattr(newVisit, prop, getattr(self, prop))    
    return newVisit

  def delete_statistics(self):
    stats = self.visit_statistics
    if stats: stats.delete() 

  @staticmethod
  def delete_visits(visits):
    """ Delete visit and set counter """    
    objs = []
    num = 0
    for visit in visits:
      stats = visit.visit_statistics
      if stats: objs.append(stats)
      objs.append(visit)
      num += 1

    db.delete(objs)
    Visit.set_count(Visit.get_count() - num)   
  
  def put_visit(self):
    """ Put the visit, assign short string and increment visit count """
    self.assign_short_string()
    self.put()
    Visit.increment_count() 
    
  @models.permalink
  def get_view_url(self):
    return ('healthdb.views.visit_view', (),
            {'orgStr': self.get_patient().organization,
             'patientStr': self.get_patient().short_string,
             'visitStr': self.short_string})

  @models.permalink
  def get_edit_url(self):
    return ('healthdb.views.visit_edit', (),
            {'orgStr': self.get_patient().organization,
             'patientStr': self.parent().short_string,
             'visitStr': self.short_string})
    
  @staticmethod
  def get_count():
    return counter.get_count('Visit')

  @staticmethod
  def increment_count():
    return counter.increment('Visit')

  @staticmethod
  def set_count(count):
    return counter.set_value('Visit', count)

  @staticmethod
  def get_all_visits(org):
    '''Read visits and patients in bulk for given organization.'''
    logging.info("load visits")
    FETCH_SIZE = 100
    query = Visit.all().order('__key__')
    the_visits = []
    patient_keys = {}
    num = 0
    # NOTE(dan): We're supposed to be able to do this without a cursor,
    # but it hung at 1000 elements, so cursors it is.
    cursor = None
    visits = query.fetch(FETCH_SIZE)
    while visits:
      for visit in visits:
        num += 1
        if (num % 100) == 0: logging.info("Loaded %d visits" % num)
        the_visits.append(visit)
        patient_keys[visit.parent_key()] = 1
      query.with_cursor(query.cursor())
      visits = query.fetch(FETCH_SIZE)

    patient_cache = PatientCache(patient_keys.keys())
    if org:
      # Filter out visits not of the right org
      the_visits = [visit for visit in the_visits
                    if patient_cache.get_patient(
                      visit.parent_key()).organization == org]
    return patient_cache, the_visits

  def get_view_fullurl(self):
    return urlparse.urljoin(util.get_domain(), self.get_view_url())

  def get_patient(self):
    return self.parent()

  def get_visit_statistics(self):
    # TODO(dan): Implement timeout of cached statistics: 1 day
    try:
      stats = self.visit_statistics
    except db.Error, dummy:
      stats = None
      self.visit_statistics = None

    if not stats:
      visit_stats = VisitStatistics.get_stats_for_visit(self)
      if visit_stats:
        visit_stats.put()
        self.visit_statistics = visit_stats
      #logging.info("calculate VisitStatistics: %s" % visit_stats)
  
      # Cache the stats or lack thereof
      self.put()
    return self.visit_statistics

  def is_alertworthy(self):
    """Return true if any visit statistic is alertworthy."""
    return self.get_visit_statistics().is_alertworthy()

  _plumpynut_ration_table = [
    (3.5,  1.5),
    (4.0,  2.0),
    (5.5,  2.5),
    (7.0,  3.0),
    (8.5,  3.5),
    (9.5,  4.0),
    (10.5, 4.5),
    (12.0, 5.0),
    ]
  def plumpynut_ration(self):
    """Return recommended (daily, weekly) amounts of Plumpy'nut for weight.

    This is approximately kg * 200 / 500.0

    However, there is a table in the CTC Field Guide that evens this out to
    half-packets and half-kg, so we are faithful to the table.

    See page 193 of the CTC Field Guide, Annex 20 OTP RUTF Plumpy'nut Ration.
    For 92g packets containing 500 kcal, average 200 kcal/kg/day.

    CTC = Community-based Therapeutic Care
    OTP = Outpatient Therapeutic Programme
    RUTF = Ready-to-Use Therapeutic Food
    @see http://en.wikipedia.org/wiki/Plumpy'nut
    """
    daily = 1
    if self.weight >= 12: daily = 5
    elif self.weight < 3.5: daily = 1
    else:
      idx = 0
      while (self.weight > Visit._plumpynut_ration_table[idx+1][0]
             and idx < len(Visit._plumpynut_ration_table)-2):
        idx += 1
      daily = Visit._plumpynut_ration_table[idx][1]
    weekly = round(daily * 7)
    return {'daily' : daily, 'weekly' : weekly}

  @staticmethod
  def visit_stats_expanded_names():
    '''Expand Visit._visit_stat_props.

    Each ZscoreAndPercentileProperty gets two slots: x_zscore, x_percentile'''
    visit_stat_props = []
    vsprops = VisitStatistics.properties()
    for prop in Visit._visit_stat_prop_names:
      # HACK(dan): Expand ZscoreAndPercentileProperty names into 2:
      # x_zscore, x_percentile
      # This is a hack because the printing actually takes place in
      # util.csv_line()
      if isinstance(vsprops[prop], ZscoreAndPercentileProperty):
        visit_stat_props.append('%s_zscore' % prop)
        visit_stat_props.append('%s_percentile' % prop)
      else:
        visit_stat_props.append(prop)
    return visit_stat_props

  @staticmethod
  def export_csv_header():
    patient_prop_names = ",".join(map(lambda x: 'patient_' + x,
                                      Visit._patient_prop_names))
    visit_prop_names = ",".join(map(lambda x: 'visit_' + x,
                                    Visit._visit_prop_names))
    visit_stat_props = Visit.visit_stats_expanded_names()
    visit_stat_prop_names = ",".join(visit_stat_props)
    return (patient_prop_names
            + "," + visit_prop_names
            + "," + visit_stat_prop_names)

  def export_csv_line(self, patient):
    '''A line of CSV values representing this visit and patient.

    It is in the same order as export_csv_header.
    Use the patient passed in so that we can load patients in bulk.
    '''
    assert patient.key() == self.parent_key()
    patient_line = util.csv_line(Visit._patient_prop_names,
                                 Patient.properties(),
                                 patient)
    visit_line = util.csv_line(Visit._visit_prop_names,
                               Visit.properties(),
                               self)
    visit_stats = self.get_visit_statistics()
    if visit_stats:
      visit_stats_line = util.csv_line(Visit._visit_stat_prop_names,
                                       VisitStatistics.properties(),
                                       self.get_visit_statistics())
    else:
      visit_stat_props = []
      for dummy in range(len(Visit.visit_stats_expanded_names())):
        visit_stat_props.append('')
      visit_stats_line = ",".join(visit_stat_props)

    return patient_line + "," + visit_line + "," + visit_stats_line

# Patient properties to export
Visit._patient_prop_names = sorted(util.printable_properties(Patient).keys())
# Visit properties to export
Visit._visit_prop_names = sorted(util.printable_properties(Visit).keys())
# VisitStatistics properties to export
Visit._visit_stat_prop_names = sorted(util.printable_properties(
                                             VisitStatistics).keys())


# These VisitStatistics maps are down here because they need Visit constants
VisitStatistics.SEX_MAP = { Patient.MALE: VisitStatistics.GROWTHSERVER_MALE,
                            Patient.FEMALE: VisitStatistics.GROWTHSERVER_FEMALE }
VisitStatistics.HEIGHT_POSITION_MAP = {
                      Visit.STANDING: VisitStatistics.GROWTHSERVER_STANDING,
                      Visit.RECUMBENT: VisitStatistics.GROWTHSERVER_RECUMBENT }
