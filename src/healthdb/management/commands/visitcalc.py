""" A script for calculating cached latest_visit statistics on patients.

This is a manage.py command.  Run with --help for documentation.

Example usage:

To run on localhost:
> manage.py visitcalc

To run on production:
> manage.py visitcalc --remote
"""

import getpass
import logging
import settings

from django.core.management.base import BaseCommand, CommandError

from google.appengine.ext.remote_api import remote_api_stub
from google.appengine.ext import db

from optparse import make_option

from healthdb import models

def auth_func():
  """Get username and password (for access to localhost)"""
  return raw_input('Username:'), getpass.getpass('Password:')

# Number of rows to read/write at once
ROWS_PER_BATCH = 200

class LoadError():
  def __init__(self, msg):
    self.msg = msg
  def __str__(self):
    return self.msg

def set_patient_visit_stats():
  '''Set latest_visit statistics on Patient instances.

  NOTE: This is not accurate if data is added while this is
  happening, but it's not a problem for now. 
  '''
  pats = models.Patient.all().order('__key__').fetch(ROWS_PER_BATCH)
  count = 0
  while pats:
    pats_to_put = []
    for pat in pats:
      try:
        if pat.set_latest_visit(force=True, put = False):
          pats_to_put.append(pat)
      except TypeError, err:
        logging.info('Skip patient %s: %s' % (pat.short_string, err))
    db.put(pats_to_put)

    count += len(pats)
    logging.info('Set %d visit caches' % count)

    pats = models.Patient.all().order('__key__').filter(
      '__key__ >', pats[-1].key()).fetch(ROWS_PER_BATCH)


class Command(BaseCommand):
  option_list = BaseCommand.option_list + (
    make_option('--app-id', dest='app_id', help='The app id'),
    make_option('--host', dest='host', default='localhost:8080',
      help='Specifies the URL of the local application.  Use -- remote '
           'to modify the production site.'),
  )
  help = 'Sets counts'
  args = ''

  def handle(self, *app_labels, **options):
    # Turn off copious DEBUG logging
    logging.getLogger().setLevel(logging.INFO)

    # Note: this app is only supported for decisionapp
    if len(app_labels) != 0:
      raise CommandError("This command doesn't take a list of parameters"
                         "...it only runs against the 'childdb' app.")

    app_id = options.get('app_id')
    if not app_id:
      raise CommandError('Must give --app-id')

    # Configure local server to run against, if we're not --remote
    # TODO(max): I couldn't get this to run against the correct local
    #   instance of the datastore, so we'll connect this way.  It remains
    #   a TODO to just run this script directly, without this block.
    remote = options.get('remote') # None==local, True==remote (production)
    if not remote:
      remote_api_url = settings.DATABASE_OPTIONS['remote_url']
      host = options.get('host')
      remote_api_stub.ConfigureRemoteDatastore(
        "childdb", remote_api_url, auth_func, host)

    set_patient_visit_stats()
