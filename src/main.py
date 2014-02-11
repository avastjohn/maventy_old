import logging

# GAE Patch main():
from common.appenginepatch.main import *

# Our own patches follow:

# Local imports
import db_log
import db_cache

# Verify that we're running django 1.0 or later
logging.info('django.__file__ = %r, django.VERSION = %r',
             django.__file__, django.VERSION)
assert django.VERSION[0] >= 1, "This Django version is too old"

def log_exception(*args, **kwds):
  """Django signal handler to log an exception."""
  cls, err = sys.exc_info()[:2]
  logging.exception('Exception in request: %s: %s', cls.__name__, err)

# Log all exceptions detected by Django.
django.core.signals.got_request_exception.connect(log_exception)

def our_profile_main():
  db_log.clear_callmap()
  db_log.clear_requestmap()

  # From appenginepatch
  profile_main()

  db_log.log_callmap()

# Turn on logging of profiling results
#main = our_profile_main
# No profiling.  real_main is from appenginepatch.
main = real_main

# Turn on per-request cache of datastore calls
db_cache.patch_db_get()
# assert there was no across-request caching
assert 0 == db_cache.get_cache_size()

# Turn on logging of datastore calls
#db_log.patch_appengine()

# We have to be logging debug level to see messages from db_cache or db_log
#logging.getLogger().setLevel(logging.DEBUG)
#logging.debug('Set logging level to DEBUG')


if __name__ == '__main__':
  main()
