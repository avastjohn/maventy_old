import getpass
import settings
import logging

from django.core.management.base import BaseCommand, CommandError

from google.appengine.ext.remote_api import remote_api_stub
from optparse import make_option


def auth_func():
  """Get username and password (for access to localhost)"""
  # TODO(dan): Make 'Username:' go to stderr instead of stdout
  return raw_input('Username:'), getpass.getpass('Password:')

# TODO(dan): Factor out app-id, host, etc.
class ManageCommand(BaseCommand):
  option_list = BaseCommand.option_list + (
    make_option('--app-id', dest='app_id', help='The app id'),
    make_option('--host', dest='host', default='localhost:8080',
      help='Specifies the URL of the local application.  Use -- remote '
           'to modify the production site.'),
  )
  args = ''

  def connect(self, *app_labels, **options):
    # Turn off copious DEBUG logging
    logging.getLogger().setLevel(logging.INFO)

    # Note: this app is only supported for decisionapp
    if len(app_labels) != 0:
      raise CommandError("This command doesn't take a list of parameters"
                         "...it only runs against the 'childdb' app.")

    app_id = options.get('app_id')
    # NOTE(dan): Local app requires you NOT to give --app-id
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
