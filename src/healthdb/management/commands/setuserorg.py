""" A script for updating the patient organization of a user.

This is a manage.py command.  Run with --help for documentation.

Example usage:

To run on localhost:
> manage.py setuserorg --user dfrankow --org maventy

To run on production:
> manage.py setuserorg --user dfrankow --org maventy --remote
"""

import logging
from optparse import make_option

from google.appengine.ext import db

from django.contrib.auth.models import User

from healthdb.management.commands.commandutil import ManageCommand


def set_user_org(username, org):
#  userobj = User.objects.get(username__exact=username)
  # HACK(dan): This gets the user object, but it's probably not the right way.
  userobj = User.get_by_key_name('key_' + username)
  if userobj:
    userobj.organization = org
    userobj.save()
    logging.info("Set %s organization to %s" % (username, org))
  else:
    logging.warning("No such user %s" % username)


def set_all_user_orgs_to_maventy():
  '''Iterate over all the users in the DB and set org to "maventy".
  
  This was useful once, and may be useful if we modify User.all() to some
  other query'''
  org = 'maventy'
  for userobj in User.all():
    userobj.organization = org
    userobj.save()
    logging.info("Set %s organization to %s" % (userobj.username, org))


class Command(ManageCommand):
  option_list = ManageCommand.option_list + (
    make_option('--username', dest='username', help='User name'),
    make_option('--organization', dest='organization',
      help='Organization'),
  )
#  args = ''

  help = 'set user organization'

  def handle(self, *app_labels, **options):
    self.connect(*app_labels, **options)
    set_user_org(options.get('username'), options.get('organization'))
#    set_all_user_orgs_to_maventy()
