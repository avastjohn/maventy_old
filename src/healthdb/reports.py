import models
import util

class ReportLine():
  ''' Generic report line'''
  def __init__(self, **kwds):
    self.__dict__.update(kwds)


class PatientReport():
  def __init__(self, org, visit_date_from, visit_date_to, default_country, residence):
    self.org = org
    self.visit_date_from = visit_date_from
    self.visit_date_to = visit_date_to
    self.country = default_country
    self.residence = residence

  def _get_visits(self, ordered = False):
    '''Get visits from our org in our date range.
    TODO(dan): Move to Visit.'''
    query = "WHERE organization = :1 and visit_date >= :2 and visit_date <= :3"
    if ordered: query += " ORDER BY visit_date DESC"
    
    return models.Visit.gql(query, self.org, self.visit_date_from, self.visit_date_to)

  def get_screening_data(self):
    ''' Return # of visits and # unique patients within a date range.
    '''
    report_data = []
    visit_count = 0
    visits = self._get_visits()
    patients = []
    
    # Get patients and count
    if self.residence > '':
      for visit in visits:
        if util.string_eq_nocase(visit.get_patient().residence, self.residence):
          (patients, visit_count) = add_screening_record(visit, patients, visit_count)
          #patients.append(visit.get_patient())
          #visit_count += 1
      patient_count = len(set(patients))
    elif self.country > '':
      for visit in visits:  
        if visit.get_patient().country == self.country:
          (patients, visit_count) = add_screening_record(visit, patients, visit_count)
          #patients.append(visit.get_patient())
          #visit_count += 1
      patient_count = len(set(patients))          
    else:       
      patient_count = len(set([visit.get_patient() for visit in visits])) 
      visit_count = visits.count()             
        
    # Build report
    report_data.append(ReportLine(visitcount = visit_count, patientcount=patient_count))
    return report_data

  def get_screening_details(self):
    ''' Retrieve patients that have visits within a date range in order to build a report
    '''
    # TODO(dan): Factor get_screening_data and get_screening_details
    report_detail = []
    visits = self._get_visits(ordered = True)
    
    for visit in visits:
      if self.residence > '':
        if util.string_eq_nocase(visit.get_patient().residence, self.residence):
          report_detail.append(ReportLine(patient=visit.get_patient(), visit=visit))  
      elif self.country > '':
        if visit.get_patient().country == self.country:
          report_detail.append(ReportLine(patient=visit.get_patient(), visit=visit))
      else:
        report_detail.append(ReportLine(patient=visit.get_patient(), visit=visit))
    
    return report_detail
    
  def get_undernutrition_data(self, zscore):
    ''' Retrieve undernutrition data based on zscore in order to build a report
    '''
    # TODO(dan): Factor get_undernutrition_data and get_undernutrition_detail
    report_data = []
    patients = []
    visits_latest = []
    visits = self._get_visits()
    stunted_children_counter = 0
    underweight_children_counter = 0
    wasting_children_counter = 0
    visit_counter = 0
    visit_latest_counter = 0
    
    # Get latest visit per patient
    for visit in visits:
      if self.residence > '':
        if util.string_eq_nocase(visit.get_patient().residence, self.residence):
          (patients, visits_latest, visit_counter) = add_undernutrition_record(visit, patients, visits_latest, visit_counter)
          #patients.append(visit.get_patient())
          #visits_latest.append(visit.get_patient().get_latest_visit())
          #visit_counter += 1
      elif self.country > '':
        if visit.get_patient().country == self.country:
          (patients, visits_latest, visit_counter) = add_undernutrition_record(visit, patients, visits_latest, visit_counter)
          #patients.append(visit.get_patient())
          #visits_latest.append(visit.get_patient().get_latest_visit()) 
          #visit_counter += 1     
      else:
        (patients, visits_latest, visit_counter) = add_undernutrition_record(visit, patients, visits_latest, visit_counter)          
        #patients.append(visit.get_patient())
        #visits_latest.append(visit.get_patient().get_latest_visit())
        #visit_counter += 1
            
    visits_latest = list(set(visits_latest))
    
    for visit in visits_latest:
      visit_latest_counter += 1
      # If the statistics does not exist, ignore the visit in the counts
      try:
        stats = visit.get_visit_statistics()
        if stats.length_or_height_for_age.zscore:
          if stats.length_or_height_for_age.zscore < float(zscore):
            stunted_children_counter += 1
        if stats.weight_for_age.zscore:
          if stats.weight_for_age.zscore < float(zscore):
            underweight_children_counter += 1
        if stats.weight_for_length_or_height.zscore:
          if stats.weight_for_length_or_height.zscore < float(zscore):
            wasting_children_counter += 1
      except:
        pass
    # Remove duplicate patients
    patients = list(set(patients))
    
    percent_stunted = 0
    percent_underweight = 0
    percent_wasting = 0
    total_undernourished = 0
    percent_undernourished = 0
    
    if visit_counter > 0:
      # Calculate percentages    
      percent_stunted = stunted_children_counter * 100.00 / visit_counter
      percent_underweight = underweight_children_counter * 100.00 / visit_counter
      percent_wasting = wasting_children_counter * 100.00 / visit_counter
      total_undernourished = stunted_children_counter + underweight_children_counter + wasting_children_counter
      percent_undernourished = total_undernourished * 100.00 / visit_counter
    
    # Build report
    report_data.append(ReportLine(stunted=stunted_children_counter, percentagestunted=percent_stunted,
                                  underweight=underweight_children_counter, percentageunderweight=percent_underweight,
                                  wasting=wasting_children_counter, percentagewasting=percent_wasting,
                                  totalundernourished = total_undernourished, percentundernourished = percent_undernourished,
                                  visitcount=visit_counter, patientcount=len(patients)))
    
    return report_data

  def get_undernutrition_detail(self, zscore_type, zscore):
    ''' Retrieve patients with undernutrition zscores within a date range in order to build a report
    '''
    report_detail = []
    visits = self._get_visits(ordered = True)
    for visit in visits:
      try:
        stats = visit.get_visit_statistics()
        stat = float(zscore)
        if zscore_type == 'stunted':
          stat = float(stats.length_or_height_for_age.zscore)
        elif zscore_type == 'underweight':
          stat = float(stats.weight_for_age.zscore)
        elif zscore_type == 'wasting':
          stat = float(stats.weight_for_length_or_height.zscore)
        else:
          stat = float(zscore)
          
        if stat < float(zscore):
          if self.residence > '':
            if util.string_eq_nocase(visit.get_patient().residence, self.residence):
              report_detail.append(ReportLine(patient=visit.get_patient(), visit=visit))
          elif self.country > '':
            if visit.get_patient().country == self.country:
              report_detail.append(ReportLine(patient=visit.get_patient(), visit=visit))
          else:
            report_detail.append(ReportLine(patient=visit.get_patient(), visit=visit))  
      except:
        pass
    
    return report_detail

def add_screening_record(visit, patients, visit_count):
  '''helper function
  '''
  patients.append(visit.get_patient())
  visit_count += 1
  return (patients, visit_count)
  
def add_undernutrition_record(visit, patients, visits_latest, visit_counter):
  '''helper function
  '''
  patients.append(visit.get_patient())
  visits_latest.append(visit.get_patient().get_latest_visit())
  visit_counter += 1
  return (patients, visits_latest, visit_counter)