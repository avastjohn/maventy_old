# -*- coding: utf-8 -*-

# Python imports
import logging
import math
import unittest
from xml.dom import minidom

# Local imports
import models
import util
import datetime
import counter

from growthcalc.growthcalc import VisitStatistics
import growthcalc.growthcalc

from growthcalc.growthcalc import Sex
from growthcalc.growthcalc import Measured

import csv

class TestGrowthCalculator(unittest.TestCase):
  def test1(self):    
    # Bernadette
    sex = Sex.FEMALE
    dateOfBirth = datetime.date(2005,03,21)
    dateOfVisit = datetime.date(2007,03,25)
    ageInDays = (dateOfVisit - dateOfBirth).days
    weight = 8.2 # kg
    length = 74.0 # cm
    headCircumference = 45.0 # cm
    measured = Measured.RECUMBENT
    
    loh = growthcalc.growthcalc.NormalizedLengthOrHeight(
                                                   ageInDays, length, measured)  
    bmi = growthcalc.growthcalc.heightAndWeightToBmi(loh.lengthOrHeight, weight)
    util.assertNear(self, 15.3, bmi, 0.1)
    
    anthro = growthcalc.growthcalc.Anthro()
    
    # Weight-for-length-or-height
    zscore = anthro.getWeightZscoreConfigForLengthOrHeight(
                                          Sex.map[sex], loh, weight, ageInDays)
    percentile = growthcalc.growthcalc.zscoreToPercentile(zscore)
    util.assertNear(self, -1.00, zscore, 0.01)
    util.assertNear(self, 15.9, percentile, 0.1)

    # Weight-for-age
    zscore = anthro.getWeightZscoreConfigForAge(Sex.map[sex], ageInDays, weight)
    percentile = growthcalc.growthcalc.zscoreToPercentile(zscore)
    util.assertNear(self, -2.87, zscore, 0.01)
    util.assertNear(self, 0.2, percentile, 0.1)
    
    # Length-or-height for age
    zscore = anthro.getLengthOrHeightZscoreConfigForAge(
                          Sex.map[sex], ageInDays, loh.lengthOrHeight, measured)
    percentile = growthcalc.growthcalc.zscoreToPercentile(zscore)
    util.assertNear(self, -3.87, zscore, 0.01)
    self.assertTrue(util.isNaN(percentile))
    
    # BMI-for-age
    zscore = anthro.getBodyMassIndexZscoreConfigForAge(
                       Sex.map[sex], ageInDays, bmi, weight, loh.lengthOrHeight)
    percentile = growthcalc.growthcalc.zscoreToPercentile(zscore)
    util.assertNear(self, -0.33, zscore, 0.01)
    util.assertNear(self, 37.2, percentile, 0.1)
    
    # HC-for-age
    zscore = anthro.getHeadCircumferenceZscoreConfigForAge(
                                     Sex.map[sex], ageInDays, headCircumference)
    percentile = growthcalc.growthcalc.zscoreToPercentile(zscore)
    util.assertNear(self, -1.58, zscore, 0.01)
    util.assertNear(self, 5.8, percentile, 0.1)
    
  def test2(self):
    visit_stats = VisitStatistics.get_stats(
                                            datetime.date(2005,03,21),
                                            datetime.date(2007,03,25),
                                            Sex.FEMALE, 
                                            8.2, 45, 74,
                                            Measured.RECUMBENT, None)
    
    # BMI
    util.assertNear(self, 15.3, visit_stats.body_mass_index, 0.1)
    
    # Weight-for-length-or-height
    zandp = visit_stats.get_zandp('weight_for_length_or_height')
    util.assertNear(self, -1.00, zandp.zscore, 0.01)
    util.assertNear(self, 15.9, zandp.percentile, 0.1)
    
    # Weight-for-age
    zandp = visit_stats.get_zandp('weight_for_age')
    util.assertNear(self, -2.87, zandp.zscore, 0.01)
    util.assertNear(self, 0.2, zandp.percentile, 0.1)
    
    # Length-or-height for age
    zandp = visit_stats.get_zandp('length_or_height_for_age')
    util.assertNear(self, -3.87, zandp.zscore, 0.01)
    self.assertTrue(util.isNaN(zandp.percentile))
    
    # BMI-for-age
    zandp = visit_stats.get_zandp('body_mass_index_for_age')
    util.assertNear(self, -0.33, zandp.zscore, 0.01)
    util.assertNear(self, 37.2, zandp.percentile, 0.1)
    
    # HC-for-age
    zandp = visit_stats.get_zandp('head_circumference_for_age')
    util.assertNear(self, -1.58, zandp.zscore, 0.01)
    util.assertNear(self, 5.8, zandp.percentile, 0.1)
    
  def testBmiNotNan(self):
    #tombomist is too old for most calculations, but BMI should be calculated
    visit_stats = VisitStatistics.get_stats(
                                            datetime.date(1995,03,21),
                                            datetime.date(2007,03,25),
                                            Sex.MALE,
                                            30, 49.5, 140,
                                            Measured.STANDING, None)
    util.assertNear(self, 15.3, visit_stats.body_mass_index, 0.1)
    
  def testBmiNan(self):
    # Height is too small, return NaN
    self.assertTrue(util.isNaN(
                        growthcalc.growthcalc.heightAndWeightToBmi(37.99, 24)))
    # Weight is too small, return NaN
    self.assertTrue(util.isNaN(
                          growthcalc.growthcalc.heightAndWeightToBmi(50, 0.8)))
    
  def testHCforAgeNaN(self):
    # Head circumference is calculated slightly differently from other
    # stats in a way that should make it come out NaN.
    # This is "computeFinalZScore" from zscoreOtherRestricted.
    # Equivalent to AA8 in the anthrotest.csv.
    visit_stats = VisitStatistics.get_stats(
                                            datetime.date(2007,12,14),
                                            datetime.date(2008,02,29),
                                            Sex.FEMALE,
                                            8, 24.99, 63,
                                            Measured.STANDING, None)
    
    # HC-for-age
    zandp = visit_stats.get_zandp('head_circumference_for_age')
    self.assertTrue(util.isNaN(zandp.zscore))
    self.assertTrue(util.isNaN(zandp.percentile))
    
  def testLengthOrHeightForAgeNotNan(self):
    # Age is right on the border, but still valid.
    # Equivalent to AA2 in the anthrotest.csv.
    visit_stats = VisitStatistics.get_stats(
                                            datetime.date(2002,03,15),
                                            datetime.date(2007,04,14),
                                            Sex.MALE,
                                            10, 50, 65.6,
                                            Measured.RECUMBENT, None)
     
    # Length-or-height for age
    zandp = visit_stats.get_zandp('length_or_height_for_age')
    util.assertNear(self, -9.76, zandp.zscore, 0.01)
    self.assertTrue(util.isNaN(zandp.percentile))
     
  def testZeroDayStats(self):
    # Age is 0 days, whcih is still valid.
    # Equivalent to AA2 in the anthrotest.csv
    visit_stats = VisitStatistics.get_stats(
                                            datetime.date(2009,11,27),
                                            datetime.date(2009,11,27),
                                            Sex.FEMALE,
                                            4, 35, 49,
                                            Measured.RECUMBENT, None)
    
    # Length-or-height for age
    zandp = visit_stats.get_zandp('length_or_height_for_age')
    util.assertNear(self, -0.08, zandp.zscore, 0.01)
    util.assertNear(self, 46.8, zandp.percentile, 0.1)
     
  def testFile(self):
    lineNum = 0
    for row in csv.DictReader(open('growthcalc/anthrotest.csv')):
      lineNum += 1
      # The first fields are the visit
      name = row['name']
      sex = row['sex']
      
      try:
        dateOfBirth = datetime.datetime.strptime(row['dateOfBirth'], "%m/%d/%Y")   
      except:
        dateOfBirth = None
      
      try:
        dateOfVisit = datetime.datetime.strptime(row['dateOfVisit'], "%m/%d/%Y")
      except:
        dateOfVisit = None
        
      weight = float(row['weight'])
      height = float(row['lengthOrHeight'])
      headCircumference = float(row['headCircumference'])
      measured = row['measured']
      if row['oedema'] == "TRUE":
        oedema = True
      elif row['oedema'] == "FALSE":
        oedema = False

      visit_stats = VisitStatistics.get_stats(dateOfBirth,
                                              dateOfVisit,
                                              sex,
                                              weight,
                                              headCircumference,
                                              height,
                                              measured,
                                              oedema,
                                              None)
      
      testScore = float(row['bmi'])
      eps = float(row['bmi-eps'])
      self.assertTrue(util.isNanOrNear(
                                   testScore, visit_stats.body_mass_index, eps))
          
      testScore = float(row['weight-for-length-or-height'])
      eps = float(row['weight-for-length-or-height-eps'])
      zandp = visit_stats.get_zandp('weight_for_length_or_height')
      util.assertIsNanOrNear(self, testScore, zandp.zscore, eps)        
      testScore = float(row['weight-for-length-or-height-%'])
      eps = float(row['weight-for-length-or-height-%-eps'])
      util.assertIsNanOrNear(self, testScore, zandp.percentile, eps)        
      
      testScore = float(row['weight-for-age'])
      eps = float(row['weight-for-age-eps'])
      zandp = visit_stats.get_zandp('weight_for_age')
      util.assertIsNanOrNear(self, testScore, zandp.zscore, eps)
      testScore = float(row['weight-for-age-%'])
      eps = float(row['weight-for-age-%-eps'])        
      util.assertIsNanOrNear(self, testScore, zandp.percentile, eps)        
      
      testScore = float(row['length-or-height-for-age'])
      eps = float(row['length-or-height-for-age-eps'])
      zandp = visit_stats.get_zandp('length_or_height_for_age')
      self.assertTrue(util.isNanOrNear(testScore, zandp.zscore, eps))
      testScore = float(row['length-or-height-for-age-%'])
      eps = float(row['length-or-height-for-age-%-eps'])
      self.assertTrue(util.isNanOrNear(testScore, zandp.percentile, eps))
      
      testScore = float(row['bmi-for-age'])
      eps = float(row['bmi-for-age-eps'])
      zandp = visit_stats.get_zandp('body_mass_index_for_age')
      self.assertTrue(util.isNanOrNear(testScore, zandp.zscore, eps))
      testScore = float(row['bmi-for-age-%'])
      eps = float(row['bmi-for-age-%-eps'])
      self.assertTrue(util.isNanOrNear(testScore, zandp.percentile, eps))
     
      testScore = float(row['head-circumference-for-age'])
      eps = float(row['head-circumference-for-age-eps'])
      zandp = visit_stats.get_zandp('head_circumference_for_age')
      self.assertTrue(util.isNanOrNear(testScore, zandp.zscore, eps))
      testScore = float(row['head-circumference-for-age-%'])
      eps = float(row['head-circumference-for-age-%-eps'])
      self.assertTrue(util.isNanOrNear(testScore, zandp.percentile, eps))
    self.assertEquals(lineNum, 23)

class TestUtilFunctions(unittest.TestCase):
  def test_random_string(self):
    self.assertEquals(6, len(util.random_string(6)))

class TestVaccination(unittest.TestCase):
  def test_cmp(self):
    vacc1 = models.Vaccination()
    vacc2 = models.Vaccination([datetime.date(2011, 01, 02)])
    self.assertTrue(vacc1 < vacc2)
    self.assertEquals(vacc1, vacc1)
    self.assertEquals(vacc2, vacc2)

    vacc1 = models.Vaccination([datetime.date(2011, 01, 02)])
    self.assertEquals(vacc1, vacc2, 'vacc1 %s vacc2 %s' % (vacc1, vacc2))

    vacc2 = models.Vaccination([datetime.date(2011, 01, 02),
                                datetime.date(2011, 01, 04)])
    self.assertTrue(vacc1 < vacc2)
    self.assertEquals(vacc2, vacc2)
    vacc1 = models.Vaccination([datetime.date(2011, 01, 02),
                                datetime.date(2011, 01, 03)])
    self.assertTrue(vacc1 < vacc2)
    vacc1 = models.Vaccination([datetime.date(2011, 01, 02),
                                datetime.date(2011, 01, 04)])
    self.assertEquals(vacc1, vacc2)
    self.assertNotEquals(vacc1, None)

    # One None and a whole bunch of None-s are both "no vaccinations"
    # NOTE(dan): I don't remember exactly why this test, but it's certainly
    # not true now.  Looking at __cmp__, it does not have this behavior.
    #vacc1 = None
    #vacc2 = models.Vaccination([None, None])
    #self.assertEquals(vacc1, vacc2)

class TestVisitStatistics(unittest.TestCase):
  XML1 = """<growthserver_response
   date_generated="2009-10-11 23:06:02 +0000">
<input_data name="4-year-old"
 sex="MALE"
 birth_date="2004-01-01"
 visit_date="2008-01-01"
 weight="8.0" height="80.0"
 height_position="STANDING"/>
<results
 age_in_days="1461"
  body_mass_index="12.499999999999998"
  weight_for_length_or_height_percentile="NaN"
  weight_for_length_or_height_zscore="-3.496213483402183"
  weight_for_age_percentile="NaN"
  weight_for_age_zscore="-5.199346767107546"
  length_or_height_for_age_percentile="NaN"
  length_or_height_for_age_zscore="-5.561991772846775"
  body_mass_index_for_age_percentile="0.5035044096331265"
  body_mass_index_for_age_zscore="-2.5734132717631844"/>
</growthserver_response>
"""

  XML2 = """<!-- Generated by Maventy's growthserver -->
<growthserver_response date_generated="2009-11-14 19:32:24 +0000">
  <input_data name="Elino" sex="MALE" birth_date="2009-08-16"
   visit_date="2009-11-09" weight="4.1" height="50.0"
    height_position="STANDING"/>
  <results age_in_days="85" body_mass_index="15.95026629164089"
   weight_for_length_or_height_percentile="96.56881443755235"
   weight_for_length_or_height_zscore="1.8208887676790622"
   weight_for_age_percentile="NaN"
   weight_for_age_zscore="-3.3722543177558655"
   length_or_height_for_age_percentile="NaN"
   length_or_height_for_age_zscore="-4.988251517870643"
   body_mass_index_for_age_percentile="26.776907198167436"
   body_mass_index_for_age_zscore="-0.6195761967197162"
   head_circumference_for_age_percentile="0.22467706213683414"
   head_circumference_for_age_zscore="-2.8412706467810755"/>
</growthserver_response>
"""

  def test_parse_zscore_and_percentile(self):
    xml = TestVisitStatistics.XML1

    doc = minidom.parseString(xml)

    zandp = models.VisitStatistics._parse_zscore_and_percentile(
              u'weight_for_length_or_height', doc)
    self.assertTrue(util.isNaN(zandp.percentile))
    self.assertTrue(math.fabs(zandp.zscore - -3.49) < 0.01)

    visit_stats = models.VisitStatistics._parse_visit_statistics(xml)
    self.assertTrue(util.isNaN(visit_stats.weight_for_length_or_height.percentile))
    self.assertTrue(math.fabs(
                visit_stats.weight_for_length_or_height.zscore - -3.49) < 0.01)

    self.assertEquals(1461, visit_stats.age_in_days)
    self.assertTrue(math.fabs(12.5 - visit_stats.body_mass_index) < 0.01)

    # Try datastore code
    visit_stats.put()
    id = visit_stats.id
    self.assertTrue(id is not None)

    # Try str()
    foo = str(visit_stats)
    self.assertTrue(foo is not None)


  def test_parse_zscore_and_percentile_with_head_circumference_stats(self):
    xml = TestVisitStatistics.XML2

    doc = minidom.parseString(xml)

    zandp = models.VisitStatistics._parse_zscore_and_percentile(
              u'weight_for_length_or_height', doc)
    self.assertTrue(math.fabs(zandp.percentile - 96.6) < 0.1)
    self.assertTrue(math.fabs(zandp.zscore - 1.82) < 0.01)

    zandp = models.VisitStatistics._parse_zscore_and_percentile(
              u'head_circumference_for_age', doc)
    self.assertTrue(math.fabs(zandp.percentile - 0.2) < 0.1)
    self.assertTrue(math.fabs(zandp.zscore - -2.84) < 0.01)

    visit_stats = models.VisitStatistics._parse_visit_statistics(xml)
    self.assertTrue(math.fabs(
                visit_stats.head_circumference_for_age.percentile - 0.2) < 0.1)
    self.assertTrue(math.fabs(
                 visit_stats.head_circumference_for_age.zscore - -2.84) < 0.01)

    self.assertEquals(85, visit_stats.age_in_days)
    self.assertTrue(math.fabs(16.0 - visit_stats.body_mass_index) < 0.1)

    # Try datastore code
    visit_stats.put()
    id = visit_stats.id
    self.assertTrue(id is not None)

    # Try str()
    foo = str(visit_stats)
    self.assertTrue(foo is not None)

  def test_is_alertworthy(self):
    visit_stats = models.VisitStatistics._parse_visit_statistics(
                    TestVisitStatistics.XML1)
    self.assertTrue(visit_stats.is_alertworthy())
    visit_stats = models.VisitStatistics._parse_visit_statistics(
                    TestVisitStatistics.XML2)
    self.assertTrue(visit_stats.is_alertworthy())
    xml = """<growthserver_response
     date_generated="2009-11-14 20:39:51 +0000">
      <input_data name="dan" sex="MALE" birth_date="2004-01-01"
       visit_date="2005-01-01" weight="10.0" height="75.0"
        height_position="STANDING"/>
      <results age_in_days="366" body_mass_index="17.450514702931162"
       weight_for_length_or_height_percentile="66.7783773713256"
       weight_for_length_or_height_zscore="0.43380445727739364"
       weight_for_age_percentile="62.66980078419666"
       weight_for_age_zscore="0.32312372717576165"
       length_or_height_for_age_percentile="48.690119540446844"
       length_or_height_for_age_zscore="-0.03284387440408244"
       body_mass_index_for_age_percentile="68.23541425051107"
       body_mass_index_for_age_zscore="0.47429455486975625"
       head_circumference_for_age_percentile="93.31248910073958"
       head_circumference_for_age_zscore="1.4994767847047703"/>
      </growthserver_response>"""
    visit_stats = models.VisitStatistics._parse_visit_statistics(xml)
    self.assertEquals(-1.0, util.bucket_zscore(
          visit_stats.get_worst_zscore()))
    self.assertFalse(visit_stats.is_alertworthy())

    xml = """<growthserver_response
     date_generated="2009-11-14 20:39:51 +0000">
      <input_data name="dan" sex="MALE" birth_date="2004-01-01"
       visit_date="2005-01-01" weight="10.0" height="75.0"
        height_position="STANDING"/>
      <results age_in_days="366" body_mass_index="17.450514702931162"
       weight_for_length_or_height_percentile="0.1"
       weight_for_length_or_height_zscore="-3.91"
       weight_for_age_percentile="42.8"
       weight_for_age_zscore="-0.18"
       length_or_height_for_age_percentile="99.6"
       length_or_height_for_age_zscore="2.69"
       body_mass_index_for_age_percentile="1.7"
       body_mass_index_for_age_zscore="-2.13"
       head_circumference_for_age_percentile="93.31248910073958"
       head_circumference_for_age_zscore="1.4994767847047703"/>
      </growthserver_response>"""
    visit_stats = models.VisitStatistics._parse_visit_statistics(xml)
    self.assertEquals(-4.0, util.bucket_zscore(
          visit_stats.get_worst_zscore()))
    self.assertTrue(visit_stats.is_alertworthy())

  def test_nans(self):
    '''This was a bug in bucket_zscore: all zscores are NaNs'''

    xml= """
      <growthserver_response date_generated="2011-02-08 21:35:49 +0000">
        <input_data name="" sex="MALE" birth_date="2011-02-10"
         visit_date="2011-02-08"
         weight="30.0" height="40.0" height_position="STANDING"/>
        <results age_in_days="-1" body_mass_index="181.1058322114833"
         weight_for_length_or_height_percentile="NaN"
         weight_for_length_or_height_zscore="NaN"
         weight_for_age_percentile="NaN" weight_for_age_zscore="NaN"
         length_or_height_for_age_percentile="NaN"
         length_or_height_for_age_zscore="NaN"
         body_mass_index_for_age_percentile="NaN"
         body_mass_index_for_age_zscore="NaN"
         head_circumference_for_age_percentile="NaN"
         head_circumference_for_age_zscore="NaN"/>
      </growthserver_response>"""
    visit_stats = models.VisitStatistics._parse_visit_statistics(xml)
    self.assertTrue(util.isNaN(util.bucket_zscore(
          visit_stats.get_worst_zscore())))


class OtherTests(unittest.TestCase):
  def testIsNaN(self):
    self.assertFalse(util.isNaN(3.5))
    # String NaN is not float NaN.
    self.assertFalse(util.isNaN("NaN"))
    self.assertFalse(util.isNaN(u"NaN"))
    self.assertTrue(util.isNaN(util.NaN))

def set_site():
  from django.contrib.sites.models import Site
  from django.conf import settings
  #old_SITE_ID = getattr(settings, 'SITE_ID', None)
  site = Site(domain="example.com", name="example.com")
  site.save()
  settings.SITE_ID = str(site.key())

class TestPatient(unittest.TestCase):
  @staticmethod
  def make_patient():
    # patient name has non-ASCII accent, comma, and double-quote
    patient = models.Patient(name=unicode("tést ,\" name", 'utf-8'),
                             sex=models.Patient.MALE,
                             birth_date=datetime.date(2009, 11, 14),
                             country = "Madagascar", organization = "testorg")
    patient.assign_short_string()
    return patient

  def test1(self):
    patient = TestPatient.make_patient()
    url = patient.get_view_url()
    self.assertTrue(len(url) > 0)

    set_site()
    self.assertTrue(url.find('http:') == -1)
    full_url = patient.get_view_fullurl()
    self.assertTrue(len(full_url) > 0)
    self.assertTrue(full_url.find('http:') != -1)

class TestVisit(unittest.TestCase):
  def test1(self):
    patient = TestPatient.make_patient()
    patient.put()

    visit = models.Visit(parent=patient,
                         visit_date=datetime.date(2009, 11, 16), weight=10.0,
                         height=20.0, height_position=models.Visit.STANDING)
    visit.assign_short_string()
    visit.put()
    url = visit.get_view_url()
    self.assertTrue(len(url) > 0)

    set_site()
    self.assertTrue(url.find('http:') == -1)
    full_url = visit.get_view_fullurl()
    self.assertTrue(len(full_url) > 0)
    self.assertTrue(full_url.find('http:') != -1)

    # Test plumpynut_ration()
    # weight: 10
    ration = visit.plumpynut_ration()
    self.assertEqual(4.0, ration['daily'])
    self.assertEqual(28.0, ration['weekly'])

    visit.weight = 3.7
    ration = visit.plumpynut_ration()
    self.assertEqual(1.5, ration['daily'])
    self.assertEqual(11.0, ration['weekly'])

    visit.weight = 11.8
    ration = visit.plumpynut_ration()
    self.assertEqual(4.5, ration['daily'])
    self.assertEqual(32.0, ration['weekly'])

    visit.weight = 12.1
    ration = visit.plumpynut_ration()
    self.assertEqual(5, ration['daily'])
    self.assertEqual(35, ration['weekly'])

    # Test export_csv_line()
    export_line = visit.export_csv_line(patient)
    # 32 + 1 because there is an embedded comma in the name
    self.assertEqual(len(export_line.split(",")),
                     len(models.Visit.export_csv_header().split(","))+1,
                     msg = 'export_line: %s' % export_line)
    # test first value
    self.assertEqual('%s' % patient.birth_date, export_line.split(',')[0])
    # test line is unterminated
    self.assertFalse(export_line[-1] in ["\r", "\n"])

class TestCsvExport(unittest.TestCase):
  def test1(self):
    names = util.printable_properties(models.Patient).keys()
    self.assertTrue('created_date' in names)
    self.assertTrue('residence' in names)
    self.assertEqual(len(names), 12)
    #logging.info(names)

    names = util.printable_properties(models.Visit).keys()
    self.assertTrue('created_date' in names)
    self.assertTrue('short_string' in names)
    self.assertEqual(len(names), 11)
    #logging.info(names)

  def test_visit_export_header(self):
    header = models.Visit.export_csv_header()
    #logging.info(header.replace(",", "\n"))
    self.assertEqual(len(header.split(",")), 36)

class TestCounter(unittest.TestCase):
  def test1(self):
    name = "foo"
    assert counter.get_count(name) == 0
  
    counter.increment(name)
    assert counter.get_count(name) == 1
  
    counter.increment(name, 3)
    assert counter.get_count(name) == 4
  
    counter.set_value(name, 2)
    assert counter.get_count(name) == 2

class TestPatientMerge(unittest.TestCase):
  @staticmethod
  def make_patient_with_visit(patientName):
    patient = models.Patient(name=patientName, sex=models.Patient.MALE,
                             birth_date=datetime.date(2009, 11, 14),
                             country = "Madagascar", residence="test",
                             caregiver_name="test", 
                             organization="maventy",
                             bcg_vaccinations=models.Vaccination([datetime.date(2011, 01, 02)]),
                             deworming_vaccinations=models.Vaccination([datetime.date(2011, 01, 03)]), 
                             polio_vaccinations=models.Vaccination([None, None, None, None, None]),
                             dtc_vaccinations=models.Vaccination([None, None, None]),
                             hepb_vaccinations=models.Vaccination([None, None, None]),
                             measles_vaccinations=models.Vaccination([None, None, None]),
                             hib_vaccinations=models.Vaccination([None, None]),
                             vita_vaccinations=models.Vaccination([None, None, None]))
    
    patient.assign_short_string()
    patient.put()
    models.Patient.increment_count()
    visit = models.Visit(parent=patient, evaluator_name="test",
                         visit_date=datetime.date(2011, 01, 01),
                         weight=8.0, height=70.0)
    visit.put_visit()
    
    return patient
      
  def test_patient_equal(self):
    # patients that are equal
    patient1 = TestPatientMerge.make_patient_with_visit("Tom")
    patient2 = TestPatientMerge.make_patient_with_visit("Tom")
    
    message = models.Patient.merge_compare_patients(patient1, patient2)
    self.assertEquals(patient1.bcg_vaccinations, patient2.bcg_vaccinations)
    self.assertEquals('', message)
    
    patient1.delete()
    patient2.delete()
    models.Patient.set_count(models.Patient.get_count() - 2)
    
  def test_patient_not_equal(self):
    # patients that are not equal
    patient1 = TestPatientMerge.make_patient_with_visit("Tom")
    patient2 = TestPatientMerge.make_patient_with_visit("Tim")
    
    message = models.Patient.merge_compare_patients(patient1, patient2)
    # names are compared case-insensitively, so the error is lowercase.
    # not great, but truth.
    self.assertEquals('name: tom is not equal to tim', message)
    
    patient1.delete()
    patient2.delete()
    models.Patient.set_count(models.Patient.get_count() - 2)
        
              
class TestVisitDelete(unittest.TestCase):
          
  def test_create_delete(self):
    # create a patient
    patient = TestPatientMerge.make_patient_with_visit("Edit")
    assert patient
    # add visits to patient
    counter = [1,2,3]
    for i in counter:
      visit = models.Visit(parent=patient, evaluator_name="test",
                         visit_date=datetime.date(2011, 01, 01),
                         weight=8.0, height=70.0)
      visit.put_visit()

    visits = patient.get_visits()
    models.Visit.delete_visits(visits)
    patient.delete()  
    models.Patient.set_count(models.Patient.get_count() - 1)
      
class TestStringEqNoCase(unittest.TestCase):
  def test_function(self):
    self.assertFalse(util.string_eq_nocase('Anivorano', None))
    self.assertFalse(util.string_eq_nocase('Anivorano', 'Andranonakoho'))
    self.assertTrue(util.string_eq_nocase('Anivorano', 'anivorano'))
    self.assertTrue(util.string_eq_nocase('Anivorano', 'Anivorano'))
    self.assertTrue(util.string_eq_nocase(None, None))
    self.assertTrue(util.string_eq_nocase('Anivorano', ''))
    