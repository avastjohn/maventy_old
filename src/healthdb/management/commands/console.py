""" A script for running a console.

This is a manage.py command.  Run with --help for documentation.

Example usage:

To run on localhost:
> manage.py console --app_id <appid>

To run on production:
> manage.py console --remote --app_id <appid>
"""

import getpass
import logging
import settings
import code

from django.core.management.base import BaseCommand, CommandError

from google.appengine.ext.remote_api import remote_api_stub

from optparse import make_option

def auth_func():
  """Get username and password (for access to localhost)"""
  return raw_input('Username:'), getpass.getpass('Password:')



def console(app_id):
  code.interact('App Engine interactive console for %s' % (app_id,),
              None, locals())


class Command(BaseCommand):
  option_list = BaseCommand.option_list + (
    make_option('--app-id', dest='app_id', help='The app id'),
    make_option('--host', dest='host', default='localhost:8080',
      help='Specifies the URL of the local application.  Use -- remote '
           'to modify the production site.'),
  )
  help = 'Runs a console'
  args = ''

  def handle(self, *app_labels, **options):
    # Turn off copious DEBUG logging
    logging.getLogger().setLevel(logging.INFO)

    app_id = options.get('app_id')
    if not app_id:
      raise CommandError('Must give --app-id')
  
    # Note: this app is only supported for healthdb
    if len(app_labels) != 0:
      raise CommandError("This command doesn't take a list of parameters"
                         "...it only runs against the 'childdb' app.")

    # TODO(dan): Factor this out
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

    console(app_id)
