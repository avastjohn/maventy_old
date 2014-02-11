""" A script for updating the search index.

This is a manage.py command.  Run with --help for documentation.

Example usage:

To run on localhost:
> manage.py updatesearchindex

To run on production:
> manage.py updatesearchindex --remote
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

def update_search_index():
  '''Set count of class instances.

  NOTE: This is not accurate if data is added while this count is
  happening, but it's not a problem for now. 
  '''
  count = 0
  pats = models.Patient.all().order('__key__').fetch(ROWS_PER_BATCH)
  while pats:
    count += len(pats)
    # This is terribly expensive.
    # TODO(dan): Might be able to call search.core.post, but it's complicated
    db.put(pats)
    logging.info('Updated %d' % count)

    pats = models.Patient.all().order('__key__').filter(
      '__key__ >', pats[-1].key()).fetch(ROWS_PER_BATCH)

  logging.info('Updated %d' % (count))

# TODO(dan): Factor out app-id, host, etc.
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
        app_id, remote_api_url, auth_func, host)

    update_search_index()
