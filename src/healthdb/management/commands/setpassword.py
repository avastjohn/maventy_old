""" A script for updating the patient organization of a user.

This is a manage.py command.  Run with --help for documentation.

Example usage:

To run on localhost:
> manage.py setpassword --user dfrankow --password foo

To run on production:
> manage.py setpassword --user dfrankow --password foo --remote
"""

import logging
import sys

from optparse import make_option

from google.appengine.ext import db

from django.contrib.auth.models import User

from healthdb.management.commands.commandutil import ManageCommand


def set_password(username, password):
#  userobj = User.objects.get(username__exact=username)
  # HACK(dan): This gets the user object, but it's probably not the right way.
  userobj = User.get_by_key_name('key_' + username)
  if userobj:
    userobj.set_password(password)
    userobj.save()
    logging.info("Set password for %s" % username)
  else:
    logging.warning("No such user %s" % username)


class Command(ManageCommand):
  option_list = ManageCommand.option_list + (
    make_option('--username', dest='username', help='User name'),
    make_option('--password', dest='password', help='Password'),
  )
#  args = ''

  help = 'set user password'

  def handle(self, *app_labels, **options):
    self.connect(*app_labels, **options)
    username = options.get('username')
    if not username:
      logging.error("Must give --username")
      sys.exit(1)
    password = options.get('password')
    if not password:
      logging.error("Must give --password")
      sys.exit(1)
    set_password(username, password)
