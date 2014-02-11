""" A script for adding visits to the same patient

This is a manage.py command.  Run with --help for documentation.

Example usage:

To run on localhost:
> python manage.py addmultiplevisits

To run on production:
> python manage.py addmultiplevisits --remote
"""
import getpass
import logging
import settings
import datetime

from django.core.management.base import BaseCommand, CommandError
from google.appengine.ext.remote_api import remote_api_stub
from google.appengine.ext import db
from optparse import make_option
from healthdb import models

def auth_func():
  """Get username and password (for access to localhost)"""
  return raw_input('Username:'), getpass.getpass('Password:')

ROWS_PER_BATCH = 50

def run():
  count = 0
  visits = models.Visit.all().order('__key__').fetch(ROWS_PER_BATCH)
  while visits:
    visits_to_save = []
    for visit in visits:
        if not visit.short_string:
          visit.assign_short_string()
          visits_to_save.append(visit)
    db.put(visits_to_save)
    visits_to_save = [] 
    count += len(visits)    
    logging.info('Updated %d visits' % count)  
    visits = models.Visit.all().order('__key__').filter('__key__ >', visits[-1].key()).fetch(ROWS_PER_BATCH)


class Command(BaseCommand):
  option_list = BaseCommand.option_list + (
    make_option('--app-id', dest='app_id', help='The app id'),
    make_option('--host', dest='host', default='localhost:8080',
      help='Specifies the URL of the local application.  Use -- remote '
           'to modify the production site.'),
  )
  help = 'Adds multiple visits to a patient'
  args = ''
    
class Command(BaseCommand):
  option_list = BaseCommand.option_list + (
    make_option('--app-id', dest='app_id', help='The app id'),
    make_option('--host', dest='host', default='localhost:8080',
      help='Specifies the URL of the local application.  Use -- remote '
           'to modify the production site.'),
  )
  help = 'add multiple visits to a patient'
  args = ''
  
  def handle(self, *app_labels, **options):
    logging.getLogger().setLevel(logging.INFO)
    if len(app_labels) != 0:
      raise CommandError("This command doesn't take a list of parameters"
                         "...it only runs against the 'childdb' app.")

    app_id = options.get('app_id')
    remote = options.get('remote')
    if not remote:
      remote_api_url = settings.DATABASE_OPTIONS['remote_url']
      host = options.get('host')
      remote_api_stub.ConfigureRemoteDatastore(
        app_id, remote_api_url, auth_func, host)

    run()
