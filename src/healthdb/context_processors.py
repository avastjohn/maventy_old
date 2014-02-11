# Python imports

# Local imports
import models

def vars(request):
  '''Make some variables globally available in templates'''

  is_mobile_browser = request.get_host() in [
                                 'm.childhealth.maventy.org',
                                 # Uncomment this to test mobile browser in
                                 # the default development environment:
                                 #'localhost:8080'
                                 ]
  #import logging
  #logging.info("request.get_host() '%s' (is_mobile %s)" %
  #             (request.get_host(), is_mobile_browser))
  return {'countries': models.Patient.country.choices,
          'is_mobile_browser': is_mobile_browser}
