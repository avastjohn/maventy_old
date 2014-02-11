'''
Created on Sep 18, 2011

@author: mike
'''

import logging
import healthdb.util
import math

from xml.dom import minidom
import time
from datetime import datetime

from google.appengine.ext import db
from google.appengine.api import datastore_errors

import urllib2
import urllib
from xml.parsers.expat import ExpatError
import csv

# Boundaries for input values from WHO's AnthroComputation.cs.

# The min weight for a child, in kg.
input_minweight = 0.9
# The max weight for a child, in kg.
input_maxweight = 58
# The min length/height for a child, in cm.
input_minlengthorheight = 38
# The max length/height for a child, in cm.
input_maxlengthorheight = 150
# The min HC for a child, in cm.
input_minhc = 25
# The max HC for a child, in cm.
input_maxhc = 64

# Correction used for converting from recumbent to standing
heightcorrection = 0.7
# cutoff number of days for converting from recumbent to standing
height_mindays = 731

# The min age for a child.
mindays = 0
# The max age for a child to be considered in calculations.
maxdays = 1856
# The min length, in cm (WHO standard).
minlength = 45
# The max length, in cm (WHO standard).
maxlength = 110
# The min height, in cm (WHO standard).
minheight = 65
# The max height, in cm (WHO standard).
maxheight = 120

class Sex:
  MALE="MALE"
  FEMALE="FEMALE"
  
  map = {}
  map[MALE] = 1
  map[FEMALE] = 2
  
class Measured:
  STANDING="STANDING"
  RECUMBENT="RECUMBENT"

def calculate_scores(pmap, visit=None):  
  """ This function calculates the anthropometric values based on the input
      provided by the user at the command prompt. The z-scores and
      percentiles are calculated for
 
      Weight-for-age
      Length/height-for-age
      Weight-for-length
      Weight-for-height
      BMI-for-age
      Head circumference-for-age
      
      We do not at present plan to do: Arm circumference-for-age,
      Triceps skinfold-for-age and Subscapular skinfold-for-age.
  
      This program requires access to the WHO datasets. The nine datasets
      corresponding to the nine measurements should be made available somewhere
      in the classpath. These files should be of
      .csv extension, with comma-separated values. The following are the
      file names corresponding to its measurement.
     
      Weight-for-age : weianthro.csv
      Length/height-for-age : lenanthro.csv
      Weight-for-length : wflanthro.csv
      Weight-for-height : wfhanthro.csv
      BMI-for-age : bmianthro.csv
      Head circumference-for-age : hcanthro.csv
     
      Not currently used:
      Arm circumference-for-age : acanthro.csv
      Triceps skinfold-for-age : tsanthro.csv
      Subscapular skinfold-for-age: ssanthro.csv """
      
  attrmap = {}
  attrmap['generated_date'] = datetime.now()
 
  if pmap['date_of_visit'] != None and pmap['date_of_birth'] != None:
    attrmap['age_in_days'] = (pmap['date_of_visit'] - pmap['date_of_birth']).days
  else:
    attrmap['age_in_days'] = -1
  loh = NormalizedLengthOrHeight(attrmap['age_in_days'], 
                                 pmap['length'], pmap['measured'])
  
  attrmap['weight'] = pmap['weight']
  attrmap['height'] = loh.lengthOrHeight
  if u'head_circumference' in pmap: 
    attrmap['head_circumference'] = pmap['head_circumference']

  anthro = Anthro()

  anthroConfigMap = {}
  if not pmap['hasOedema']:
    attrmap['body_mass_index'] = heightAndWeightToBmi(loh.lengthOrHeight, pmap['weight'])
    anthroConfigMap['body_mass_index_for_age'] = anthro.getBodyMassIndexZscoreConfigForAge(Sex.map[pmap['sex']], attrmap['age_in_days'], attrmap['body_mass_index'], attrmap['weight'], attrmap['height'])
    anthroConfigMap['weight_for_length_or_height'] = anthro.getWeightZscoreConfigForLengthOrHeight(Sex.map[pmap['sex']], loh, attrmap['weight'], attrmap['age_in_days'])
    anthroConfigMap['weight_for_age'] = anthro.getWeightZscoreConfigForAge(Sex.map[pmap['sex']], attrmap['age_in_days'], attrmap['weight'])    
  else:
    attrmap['body_mass_index'] = healthdb.util.NaN
    anthroConfigMap['body_mass_index_for_age'] = healthdb.util.NaN
    anthroConfigMap['weight_for_length_or_height'] = healthdb.util.NaN
    anthroConfigMap['weight_for_age'] = healthdb.util.NaN
    if 'head_circumference' in attrmap: 
      anthroConfigMap['head_circumference_for_age'] = healthdb.util.NaN

  anthroConfigMap['length_or_height_for_age'] = anthro.getLengthOrHeightZscoreConfigForAge(Sex.map[pmap['sex']], attrmap['age_in_days'], attrmap['height'], pmap['measured'])  
  if 'head_circumference' in attrmap: 
      anthroConfigMap['head_circumference_for_age'] = anthro.getHeadCircumferenceZscoreConfigForAge(Sex.map[pmap['sex']], attrmap['age_in_days'], attrmap['head_circumference'])
  
  for att in VisitStatistics.INDICATORS:
    # map key is str(att) because **attrmap requires string keys
    if att in anthroConfigMap:
      zscore = anthroConfigMap[att]
      percentile = zscoreToPercentile(zscore)
      attrmap[str(att)] = ZscoreAndPercentile(zscore, percentile)

  return healthdb.models.VisitStatistics(parent=visit, **attrmap)

class Anthro():
  """Anthro contains all the parameters for the Box-Cox score computations. """
    
  def getBodyMassIndexZscoreConfigForAge(self, sex, ageInDays, bodyMassIndex, weight, height):
    ret = healthdb.util.NaN
    hasOedema = False
    if hasOedema or ageInDays < mindays or ageInDays > maxdays or not (weight > 0 and height > 0):
      ret = healthdb.util.NaN
    else:
      config = AnthroConfig('growthcalc/bmianthro.csv', bodyMassIndex, sex, ageInDays)
      ret = zscoreFromAttribute(config)
    return ret
  
  def getWeightZscoreConfigForLengthOrHeight(self, sex, loh, weight, ageInDays):
    ret = healthdb.util.NaN
    hasOedema = False
    if hasOedema or not(input_minweight <= weight and weight <= input_maxweight):
      ret = healthdb.util.NaN
    else:
      if loh.measured == Measured.STANDING:
        config = AnthroConfig('growthcalc/wfhanthro.csv', weight, sex, loh.lengthOrHeight)
      elif loh.measured == Measured.RECUMBENT:
        config = AnthroConfig('growthcalc/wflanthro.csv', weight, sex, loh.lengthOrHeight)
      ret = zscoreFromAttribute(config)
    return ret
  
  def getWeightZscoreConfigForAge(self, sex, ageInDays, weight):
    ret = healthdb.util.NaN
    hasOedema = False
    if hasOedema or ageInDays < 0 or ageInDays > maxdays or not (input_minweight <= weight and weight <= input_maxweight):
      ret = healthdb.util.NaN
    else:
      config = AnthroConfig('growthcalc/weianthro.csv', weight, sex, ageInDays)
      ret = zscoreFromAttribute(config)
    return ret
  
  def getLengthOrHeightZscoreConfigForAge(self, sex, ageInDays, height, measured):
    ret = healthdb.util.NaN
    if ageInDays < 0 or ageInDays > maxdays or not (height >= 1):
      ret = healthdb.util.NaN
    else:
      config = AnthroConfig('growthcalc/lenanthro.csv', height, sex, ageInDays)
      ret = zscoreFromAttribute(config)
    return ret
  
  def getHeadCircumferenceZscoreConfigForAge(self, sex, ageInDays, headCircumference):
    ret = healthdb.util.NaN
    if ageInDays < 0 or ageInDays > maxdays or not (input_minhc <= headCircumference and headCircumference <= input_maxhc):
      ret = healthdb.util.NaN
    else:
      config = AnthroConfig('growthcalc/hcanthro.csv', headCircumference, sex, ageInDays)
      ret = zscoreFromAttribute(config)
    return ret 
    
def zscoreFromAttribute(anthroConfig):
  """ Return a restrictred zscore from a map of data filename and physical 
  attributes.
  
  The filename must fit the design of a WHO data file defined as:
  
  sex,[age|height|length],l,m,s,[loh]
  
  sex: 1 indicating MALE, 2 indicating FEMALE
  age: age in days since birth
  height: height in cm
  length: length in cm
  l: power,
  m: median, and 
  s: variation coefficient as used in calculating zscore
  loh: 'L' for length, 'H' for height """
  for row in csv.DictReader(open(anthroConfig.fileName)):
    if 'age' in row:
      dataAgeHeightOrLength = row['age']
    elif 'length' in row:
      dataAgeHeightOrLength = row['length']
    elif 'height' in row:
      dataAgeHeightOrLength = row['height']
    if int(row['sex']) == anthroConfig.sex and float(dataAgeHeightOrLength) == anthroConfig.ageHeightOrLength:
      return zscoreOtherRestricted(anthroConfig.measureKey, float(row['l']), float(row['m']), float(row['s']), True)    
  return healthdb.util.NaN

def zscoreOtherRestricted(measure, power, median, variationCoefficient, computeFinalZScore):
  """Return a restricted zscore.
  
  Modified as follows: 
  
  - If within -3 .. 3 inclusive, zscore
  - If outside, NaN if computeFinalZScore is false, otherwise
    extrapolated in a particular way given by the WHO standard """
  zscoreNorm = zscore(measure, power, median, variationCoefficient)
  if math.fabs(zscoreNorm) > 3 and computeFinalZScore:
    if zscoreNorm > 3:
      std3Pos = cutoff(3, power, median, variationCoefficient)
      std23Pos = std3Pos - cutoff(2, power, median, variationCoefficient)
      zscoreNorm = 3 + ((measure - std3Pos) / std23Pos)
    elif zscoreNorm < 3:
      std3Neg = cutoff(-3, power, median, variationCoefficient)
      std23Neg = cutoff(-2, power, median, variationCoefficient) - std3Neg
      zscoreNorm = -3 + ((measure - std3Neg) / std23Neg)
  return zscoreNorm
    
def zscore(measure, power, median, variationCoefficient):
  return (math.pow((measure / median), power) - 1) / (power * variationCoefficient)
  
def cutoff(desiredZscore, power, median, variationCoefficient):
  return median * (math.pow((1 + (power * variationCoefficient * desiredZscore)), (1 / power)))

def heightAndWeightToBmi(height, weight):
  """standard metric conversion from weight and height to BMI, height in cm, weight in kg"""
  if weight < input_minweight or weight > input_maxweight or height < input_minlengthorheight or height > input_maxlengthorheight:
    output = healthdb.util.NaN
  else:
    output = weight / ((height / 100.0) ** 2.0)        
  return output

def zscoreToPercentile(zscore):
  """Produce a number between 0 and 100 inclusive that is the percentile for
     the given zscore, or Double.NaN if the zscore is outside of -3 to 3."""
  retVal = healthdb.util.NaN
  # WHO technical specs chapter 7: "However, a restriction was imposed on
  # all indicators to enable the derivation of percentiles only within
  # the interval corresponding to z-scores between -3 and 3. The
  # underlying reasoning is that percentiles beyond +-3 SD are invariant
  # to changes in equivalent z-scores. The loss accruing to this
  # restriction is small since the inclusion range corresponds to the
  # 0.135th to 99.865th percentiles."
  if math.fabs(zscore) <= 3:
    absVal = math.fabs(zscore)
    P1 = (1 - 1 / math.sqrt(2 * math.pi) * math.exp(-math.pow(absVal, 2) / 2)
                * (
                0.31938 * (1 / (1 + 0.2316419 * absVal))
                - 0.356563782 * math.pow((1 / (1 + 0.2316419 * absVal)), 2)
                + 1.781477937 * math.pow((1 / (1 + 0.2316419 * absVal)), 3)
                - 1.82125 * math.pow((1 / (1 + 0.2316419 * absVal)), 4)
                + 1.330274429 * math.pow((1 / (1 + 0.2316419 * absVal)), 5)
                ))
    
    if zscore > 0:
      P1 = P1 * 100
    else:
      P1 = 100 - P1 * 100
      
    if 0 <= P1 and P1 <= 100:
      retVal = P1
  return retVal

class NormalizedLengthOrHeight():
  """Adjust length-or-height by whether person is standing or recumbent (lying 
  down)."""
  def __init__(self, ageInDays, lengthOrHeight, measured):
    self.lengthOrHeight = lengthOrHeight
    self.measured = measured
    
    if lengthOrHeight < input_minlengthorheight or lengthOrHeight > input_maxlengthorheight:
      self.lengthOrHeight = healthdb.util.NaN
    
    if ageInDays >= height_mindays and measured == Measured.RECUMBENT:
      self.lengthOrHeight -= heightcorrection
      self.measured = Measured.STANDING
    elif 0 <= ageInDays and ageInDays < height_mindays and measured == Measured.STANDING:
      self.lengthOrHeight += heightcorrection
      self.measured = Measured.RECUMBENT

class ZscoreAndPercentile():
  """A class to contain zscore and percentile, each a float or NaN."""
  def __init__(self, zscore, percentile):
    self.zscore = zscore
    self.percentile = percentile

  def __str__(self):
    """String for debugging"""
    return "zscore %s percentile %s" % (self.zscore, self.percentile)

  def is_alertworthy(self):
    """Alertable if zscore not NaN and <0, and percentile < 25 or NaN.

    This means that this statistic shows the patient is in bad shape.
    """
    return (not healthdb.util.isNaN(self.zscore)) and self.zscore < 0 and (
            healthdb.util.isNaN(self.percentile) or (self.percentile < 25))

  def zscore_is_nan(self):
    """Return True if self.zscore is Nan, otherwise false.

    Convenience method for Django templates, which have no good logic.
    """
    return healthdb.util.isNaN(self.zscore)

  def percentile_is_nan(self):
    """Return True if self.percentile is Nan, otherwise false.

    Convenience method for Django templates, which have no good logic.
    """
    return healthdb.util.isNaN(self.percentile)

class AnthroConfig:
  def __init__(self, fileName, measureKey, sex, ageHeightOrLength):
    self.fileName = fileName
    self.measureKey = measureKey
    self.sex = sex
    self.ageHeightOrLength = ageHeightOrLength

class ZscoreAndPercentileProperty(db.Property):
  """A ZscoreAndPercentile property class."""
  data_type = ZscoreAndPercentile

  def get_value_for_datastore(self, model_instance):
    zandp = super(ZscoreAndPercentileProperty, self
                     ).get_value_for_datastore(model_instance)
    if zandp:
      zandp = str(zandp.zscore) + ':' + str(zandp.percentile)

    return zandp

  def make_value_from_datastore(self, value):
    ret = None
    if value:
      zscore, percentile = value.split(':')
      try:
        zscore = float(zscore)
      except ValueError, dummy:
        assert healthdb.util.isNaNString(zscore), 'value is %s, zscore is ' % (
                                          value, zscore)
        zscore = healthdb.util.NaN

      try:
        percentile = float(percentile)
      except ValueError, dummy:
        #logging.warning('percentile was invalid: %s' % percentile)
        # On some platforms, float('NaN') doesn't work
        assert healthdb.util.isNaNString(percentile), 'value is %s, percentile is ' % (
                                              value, percentile)
        percentile = healthdb.util.NaN

      ret = ZscoreAndPercentile(zscore, percentile)

    return ret

  def validate(self, value):
    value = super(ZscoreAndPercentileProperty, self).validate(value)
    if value is None or isinstance(value, ZscoreAndPercentile):
      return value
    elif isinstance(value, basestring):
      return self.make_value_from_datastore(value)
    raise db.BadValueError(
      "Property %s must be a ZscoreAndPercentile or string." % self.name)

class VisitStatistics(db.Model):
  # Constants for datastore
  GROWTHSERVER_MALE = Sex.MALE
  GROWTHSERVER_FEMALE = Sex.FEMALE

  GROWTHSERVER_STANDING = Measured.STANDING
  GROWTHSERVER_RECUMBENT = Measured.RECUMBENT

  # Different models computed from WHO model
  INDICATORS = [u'weight_for_length_or_height', u'weight_for_age',
                u'length_or_height_for_age', u'body_mass_index_for_age',
                u'head_circumference_for_age']

  # parent is Visit
  generated_date = db.DateTimeProperty(required=True)
  weight_for_length_or_height = ZscoreAndPercentileProperty(required=True)
  weight_for_age = ZscoreAndPercentileProperty(required=True)
  length_or_height_for_age = ZscoreAndPercentileProperty(required=True)
  body_mass_index_for_age = ZscoreAndPercentileProperty(required=True)
  head_circumference_for_age = ZscoreAndPercentileProperty(required=False)

  age_in_days = db.IntegerProperty(required=True)
  body_mass_index = db.FloatProperty(required=True)

  @property
  def id(self):
    return self.key().id()

  def __str__(self):
    return ("<VisitStatistics id=%s, generated_date=%s, "
            "age_in_days=%s, body_mass_index=%s, "
            "weight_for_length_or_height=%s, "
            "weight_for_age=%s, "
            "length_or_height_for_age=%s, "
            "body_mass_index_for_age=%s, "
            "head_circumference_for_age=%s" % (
      self.id,
      self.generated_date, 
      self.age_in_days,
      self.body_mass_index,
      self.weight_for_length_or_height,
      self.weight_for_age,
      self.length_or_height_for_age,
      self.body_mass_index_for_age,
      self.head_circumference_for_age))

  @staticmethod
  def _parse_zscore_and_percentile(att, doc):
    zandp = None
    results_elem = doc.getElementsByTagName('results')
    if results_elem:
      attp = att + u'_percentile'
      attz = att + u'_zscore'
      zscore = results_elem[0].getAttribute(attz)
      # Note: float('NaN') only works sometimes, so go by the string instead
      if zscore and not healthdb.util.isNaNString(zscore):
        zscore = float(zscore)
      else:
        zscore = healthdb.util.NaN
      percentile = results_elem[0].getAttribute(attp)
      if percentile and not healthdb.util.isNaNString(percentile):
        percentile = float(percentile)
      else:
        percentile = healthdb.util.NaN
      if zscore and percentile:
        zandp = ZscoreAndPercentile(zscore, percentile)
    return zandp

  @staticmethod
  def _parse_visit_statistics(result, visit=None):
    '''Parse an XML string from growthserver, return a VisitStatistics object with visit as its parent
    '''
    #logging.info("start parse visit obj %s" % visit)
    visit_stats = None
    try:
      doc = minidom.parseString(result)
      assert doc.documentElement.tagName == 'growthserver_response'
  
      attrmap = {}
  
      response_elem = doc.getElementsByTagName('growthserver_response')
      stime = time.strptime(response_elem[0].getAttribute('date_generated'),
                            "%Y-%m-%d %H:%M:%S +0000")
      attrmap['generated_date'] = datetime(*stime[:6])

      results_elem = doc.getElementsByTagName('results')
      att = u'age_in_days'
      attrmap[str(att)] = int(results_elem[0].getAttribute(att))
      att = u'body_mass_index'
      bmi = results_elem[0].getAttribute(att)
      try:
        bmi = float(bmi)
      except ValueError, err:
        assert healthdb.util.isNaNString(bmi), 'bmi is ' % bmi
        # TODO(dan): Unit test that NaN bmi is okay
        bmi = NaN
      attrmap[str(att)] = bmi

      if not healthdb.util.isNaN(bmi):
        try:
          for att in VisitStatistics.INDICATORS:
            # map key is str(att) because **attrmap requires string keys
            attrmap[str(att)] = VisitStatistics._parse_zscore_and_percentile(
                                                  att, doc)
    
          #print "attrmap: %s" % attrmap
          visit_stats = VisitStatistics(parent=visit, **attrmap)
        except ValueError, err:
          logging.error("Couldn't parse visit statistics xml: %s from '%s'"
                        % (err, result))
        except datastore_errors.BadValueError, err:
          logging.error("Visit statistics missing values: %s: from '%s'"
                        % (err, result))
  
    except ExpatError, err:
      logging.error("error '%s' parsing '%s'" % (err, result))

    return visit_stats

  def is_alertworthy(self):
    ret = False
    for indicator in VisitStatistics.INDICATORS:
      if hasattr(self, indicator):
        zandp = getattr(self, indicator)
        if zandp and zandp.is_alertworthy():
          ret = True
    return ret

  def get_zandp(self, indicator):
    return getattr(self, indicator)

  def get_worst_zscore(self):
    """Get the worst zscore of any indicator, NOT INCLUDING NaNs!

    We ignore NaNs because they are troublesome to sort or filter by.
    """
    worst_zscore = None
    for indicator in VisitStatistics.INDICATORS:
      if hasattr(self, indicator):
        zandp = getattr(self, indicator)
        if zandp and not healthdb.util.isNaN(zandp.zscore):
          if worst_zscore is None or worst_zscore > zandp.zscore:
#            logging.info("new worst_zscore = %s" % zandp.zscore)
            worst_zscore = zandp.zscore
#    logging.info("worst_zscore = %s" % worst_zscore)
    return worst_zscore

  # TODO(dan): Unit test this method
  @staticmethod
  def get_stats_for_visit(visit):
    patient = visit.get_patient()
    # TODO(dan): Add oedema as an attribute in future
    hasOedema = False
    return VisitStatistics.get_stats(patient.birth_date,
                                     visit.visit_date,
                                     patient.sex,
                                     visit.weight,
                                     visit.head_circumference,
                                     visit.height,
                                     visit.height_position,
                                     hasOedema,
                                     visit)

  @staticmethod
  def get_stats(birth_date, visit_date, sex, weight, head_circumference, height,
                height_position, hasOedema, visit = None):
    '''Get growth statistics from growthserver.
    
    head_circumference is optional
    sex is Patient.MALE or Patient.FEMALE
    height_position is Visit.STANDING or Visit.RECUMBENT
    '''
    # For debugging a future version:
    #rooturl = 'http://4.latest.growthserver.appspot.com/growthserver'
    rooturl = 'http://growthserver.appspot.com/growthserver'

    # TODO(dan): Return none if visit date is too far, or rather push that
    # logic to the growthserver
    pmap = {'date_of_birth': birth_date,
            'date_of_visit': visit_date,
            'sex'          : VisitStatistics.SEX_MAP[sex],
            'weight'       : weight,
            'length'       : height,
            'measured'     : VisitStatistics.HEIGHT_POSITION_MAP[height_position],
            'hasOedema'    : hasOedema,
            'format'       : 'xml'}
    # head_circumference is optional
    if head_circumference: pmap['head_circumference'] = head_circumference

    remote_growthcalc = False

    if remote_growthcalc:
      try:
        data = urllib.urlencode(pmap)
        result = urllib2.urlopen(rooturl, data)
        result_string = result.read()
        visit_stats = VisitStatistics._parse_visit_statistics(result_string, visit)
        logging.debug("result %s" % result_string)
      except urllib2.URLError, e:
        logging.error("get_stats_for_visit: %s" % e)
        visit_stats = None
    else:
      visit_stats = calculate_scores(pmap, visit)

    return visit_stats
  
  
