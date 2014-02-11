""" A script for updating the patient organization of a user.

This is a manage.py command.  Run with --help for documentation.

Example usage:

To run on localhost:
> manage.py print_all_visits --org maventy

To run on production:
> manage.py print_all_visits --org maventy --remote
"""

import logging
from optparse import make_option
import sys

from google.appengine.ext import db

from healthdb import models

from healthdb.management.commands.commandutil import ManageCommand


def print_all_visits(org):
  patient_cache, visits = models.Visit.get_all_visits(org)
  print "%s" % models.Visit.export_csv_header()
  num = 0
  for visit in visits:
    num += 1
    if (num % 100) == 0: logging.info("printed %d visits" % num)
    print(visit.export_csv_line(patient_cache.get_patient(
          visit.parent_key())))
  logging.info("printed %d visits" % num)

class Command(ManageCommand):
  option_list = ManageCommand.option_list + (
    make_option('--organization', dest='organization',
      help='Organization'),
  )

  help = 'print all visits'

  def handle(self, *app_labels, **options):
    self.connect(*app_labels, **options)
    print_all_visits(options.get('organization'))
