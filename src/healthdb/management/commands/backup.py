""" A script for backing up and restoring data.

This is a manage.py command.  Run with --help for documentation.

Example usage:

To run on localhost:
$ manage.py backup --app_id childdb

To run on production:
$ manage.py backup --app-id childdb --host childdb.appspot.com
"""

import getpass
import logging
import os
import re
import settings
import sys
import time

from django.core.management.base import BaseCommand, CommandError

from google.appengine.ext.remote_api import remote_api_stub
from google.appengine.ext import db

from optparse import make_option

def auth_func():
  """Get username and password (for access to localhost)"""
  return raw_input('Username:'), getpass.getpass('Password:')



def backup(models_to_back_up, restore, rows_per_batch):
  # Dump or restore a backup

  # For each class..
  class_counts = {}
  for model_tuple in models_to_back_up:
    #print "model_tuple: %s %s" % model_tuple
    (model_module_name, model_classes) = model_tuple
    #print "name %s classes %s" % (model_module_name, model_classes)
    for entityclass in model_classes:
      class_counts[entityclass] = 0
      print "entityclass %s" % entityclass
      imports = __import__(model_module_name, globals(), locals(),
                           [entityclass])
      MyModel = getattr(imports, entityclass)

      filename = entityclass + '.backup.txt'

      if restore:
        outfile = open(filename, 'rb')
        readmore = True
        modelobj_list = []
        while readmore:
          # Restore a backup
          line = outfile.readline()
          if not line:
            print "done reading %s" % filename
            readmore = False
          else:
            m = re.match('protobuf length: ([0-9]+)$', line)
            assert m
            protobuf_length = int(m.group(1))
            #print "%s protobuf_length %d" % (
            #  entityclass, protobuf_length)
            protobuf_str = outfile.read(protobuf_length)
            # We put a newline on the end of the protobuf
            dummy = outfile.readline()
            assert isinstance(protobuf_str, str), 'not str!'
            #print "protobuf_str: '%s'" % protobuf_str
            modelobj = db.model_from_protobuf(protobuf_str)
            # TODO(dan): warn if the object already exists
            # TODO(dan): put the object somewhere special if it can't be saved
            modelobj_list.append(modelobj)
            if len(modelobj_list) >= rows_per_batch:
              print >>sys.stderr, "Put %d %s objects" % (
                len(modelobj_list), entityclass)
              db.put(modelobj_list)
              class_counts[entityclass] += len(modelobj_list)
              modelobj_list = []

        if modelobj_list:
          print >>sys.stderr, "Put %d %s objects" % (
            len(modelobj_list), entityclass)
          db.put(modelobj_list)
          class_counts[entityclass] += len(modelobj_list)
          modelobj_list = []
      else:
        # Dump a backup
        outfile = open(filename, 'wb')

        # TODO(dan): Print the field types somewhere for verification
        #print >>outfile, yaml.dump(MyModel.properties(),
        #                           default_flow_style = False)

        entities = MyModel.all().order('__key__').fetch(rows_per_batch)
        while entities:
          for modelobj in entities:
            class_counts[entityclass] += 1
            # TODO(dan): validate_modelobj(modelobj)

            # Dump the modelobj's key and properties
            protostr = db.model_to_protobuf(modelobj).Encode()
            print >>outfile, "protobuf length: %d" % len(protostr)
            print >>outfile, protostr

          entities = MyModel.all().order('__key__').filter(
            '__key__ >', entities[-1].key()).fetch(rows_per_batch)

      outfile.close()
  print >>sys.stderr, "Final counts:"
  for entityclass in class_counts.keys():
    print >>sys.stderr, ' %s: %s' % (entityclass, class_counts[entityclass])

def check_dirs(options):
  '''Check command-line options for backupdir, end up chdir-ing into backupdir.'''
  if not os.path.exists(options.get('backupdir')) and (
     not options.get('restore')):
      print >>sys.stderr, "Make '%s' .." % options.get('backupdir')
      os.mkdir(options.get('backupdir'))

  if not os.path.isdir(options.get('backupdir')):
      print >>sys.stderr, "'%s' is not a directory" % options.get('backupdir')
      sys.exit(1)

  if not options.get('restore') and len(os.listdir(options.get('backupdir'))) > 0:
      print >>sys.stderr, ("'%s' has files in it.  Remove them first."
                           % options.get('backupdir'))
      sys.exit(1)

  os.chdir(options.get('backupdir'))


def load_config_file(config_file):
  # Get stable settings from config file
  # TODO(dan): Allow all vars to be set from file, then from command line
  if not os.path.exists(config_file):
    print >>sys.stderr, ("Give config file with --config-file (or make %s)" %
                         config_file)
  local_dict = {}
  execfile(config_file, {}, local_dict)
  appengine_root = local_dict['appengine_root']
  models_to_back_up = local_dict['models_to_back_up']

  # appenginepatch requires a few path settings for google appengine
  for a_path in [ ('google_appengine', ''),
                ('google_appengine', 'lib', 'yaml', 'lib'),
                ('google_appengine', 'lib', 'antlr3') ]:
    path_expanded = os.path.join(appengine_root, *a_path)
    #print path_expanded
    sys.path.append(path_expanded)

  return models_to_back_up


class Command(BaseCommand):
  option_list = BaseCommand.option_list + (
    make_option('--app-id', dest='app_id', help='The app id'),
    make_option('--host', dest='host', default='localhost:8080',
      help='Specifies the URL of the local application.  Use --remote '
           'to modify the production site.'),
    make_option("--restore", dest="restore",
                    help="if given, restore the specified backup-dir"
                         " (otherwise dump a new backup)",
                    action = "store_true",
                    default=False),
    make_option("-d", "--backup-dir", dest="backupdir",
                    help="directory to which (or from which) to dump "
                         "(or restore) a backup (default '%default')",
                    default="backup.%d" % time.time()),
    make_option("--rows-per-batch", dest="rows_per_batch",
                    help="# rows to fetch at once (default %default)",
                    default=100),
    make_option("--config-file", dest="config_file",
                    help="File with configuration (default %s)",
                    default = os.path.join(os.getcwd(), 'remote-backup.cfg'))
  )
  help = 'Runs a backup (or restore)'
  args = ''

  def handle(self, *app_labels, **options):
    # Turn off copious DEBUG logging
    logging.getLogger().setLevel(logging.INFO)

    app_id = options.get('app_id')
    if not app_id:
      raise CommandError('Must give --app-id')

    config_file = options.get('config_file')
    if not config_file:
      raise CommandError('Must give --config-file')

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
        app_id, remote_api_url, auth_func, host)

    check_dirs(options)

    models_to_back_up = load_config_file(config_file)

    backup(models_to_back_up, options.get('restore'),
           options.get('rows_per_batch'))
