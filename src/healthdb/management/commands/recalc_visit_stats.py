""" A script for recalculating visit statistics (by deleting and re-getting).

It recalculates only those where util.isNaN(stats.body_mass_index) is True.

This is a manage.py command.  Run with --help for documentation.

Example usage:

To run on localhost:
> manage.py recalc_visit_stats --org maventy

To run on production:
> manage.py recalc_visit_stats --org maventy --remote
"""

import logging
from optparse import make_option

from healthdb import models
from healthdb import util

from healthdb.management.commands.commandutil import ManageCommand

ROWS_PER_BATCH=200

def recalc_visit_statistics(org):
  visits = models.Visit.all().filter('organization =', org).order('__key__').fetch(ROWS_PER_BATCH)

  num = 0
  # Still don't understand why we have to iterate over visits in batches, but
  # we do, or it gets stuck at ~1000.
  while visits:
    for visit in visits:
      num += 1
      if (num % 100) == 0: logging.info("traversed %d visits" % num)
      stats = visit.get_visit_statistics()
      if util.isNaN(stats.body_mass_index):
        # recalculate by deleting and re-getting
        visit.delete_statistics()
        stats = visit.get_visit_statistics()
  
        pat = visit.get_patient()
        logging.info("Visit %s/%d has NaN BMI, recalculating stats.."
                     % (pat.short_string, visit.short_string))
  
#      pat = visit.get_patient()
#      logging.info("Visit %s/%d %s.." % (pat.short_string, visit.short_string, visit.key()))
    visits = models.Visit.all().filter('organization =', org).order('__key__').filter(
      '__key__ >', visits[-1].key()).fetch(ROWS_PER_BATCH)

  logging.info("traversed %d visits" % num)


class Command(ManageCommand):
  option_list = ManageCommand.option_list + (
    make_option('--organization', dest='organization',
      help='Organization'),
  )

  help = 'recalculate visit statistics'

  def handle(self, *app_labels, **options):
    self.connect(*app_labels, **options)
    recalc_visit_statistics(options.get('organization'))
