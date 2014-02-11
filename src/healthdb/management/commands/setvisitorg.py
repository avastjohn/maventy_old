""" A script for setting each Visit org from its parent Patient.

This is a manage.py command.  Run with --help for documentation.

Example usage:

To run on localhost:
> manage.py setvisitorg

To run on production:
> manage.py setvisitorg --remote

NOTE: This should be no longer needed once the first initialization is done.
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
ROWS_PER_BATCH = 50

def run():
  count = 0
  # TODO(dan): Shouldn't be necessary to fetch in batches, but if I don't it hangs
  visits = models.Visit.all().order('__key__').fetch(ROWS_PER_BATCH)
  visits_to_put = []
  while visits:
    for visit in visits:
      if not visit.organization:
        visit.organization = visit.get_patient().organization
        visits_to_put.append(visit)

    db.put(visits_to_put)
    visits_to_put = []
    count += len(visits_to_put)
    logging.info('Updated %d visits' % count)
    visits = models.Visit.all().order('__key__').filter(
      '__key__ >', visits[-1].key()).fetch(ROWS_PER_BATCH)

  db.put(visits_to_put)
  count += len(visits_to_put)
  logging.info('Updated %d visits. Done' % count)

# TODO(dan): Factor out app-id, host, etc.
class Command(BaseCommand):
  option_list = BaseCommand.option_list + (
    make_option('--app-id', dest='app_id', help='The app id'),
    make_option('--host', dest='host', default='localhost:8080',
      help='Specifies the URL of the local application.  Use -- remote '
           'to modify the production site.'),
  )
  help = 'Sets visit orgs'
  args = ''

  def handle(self, *app_labels, **options):
    # Turn off copious DEBUG logging
    logging.getLogger().setLevel(logging.INFO)

    # Note: this app is only supported for decisionapp
    if len(app_labels) != 0:
      raise CommandError("This command doesn't take a list of parameters"
                         "...it only runs against the 'childdb' app.")

    app_id = options.get('app_id')
    # app_id is optional for the local app
#    if not app_id:
#      raise CommandError('Must give --app-id')

    # Configure local server to run against, if we're not --remote
    # TODO(max): I couldn't get this to run against the correct local
    #   instance of the datastore, so we'll connect this way.  It remains
    #   a TODO to just run this script directly, without this block.
    remote = options.get('remote') # None==local, True==remote (production)
    if not remote:
      remote_api_url = settings.DATABASE_OPTIONS['remote_url']
      host = options.get('host')
      remote_api_stub.ConfigureRemoteDatastore(
        app_id, remote_api_url, auth_func, host)

    run()
