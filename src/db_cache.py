# Based on http://henritersteeg.wordpress.com/2009/03/30/generic-db-caching-in-google-app-engine 

import logging
import weakref

# AppEngine imports
from google.appengine.ext import db
from google.appengine.api import datastore

# define a global, weakly referenced CACHE...
_cache = weakref.WeakValueDictionary({})

# True iff patch_db_get() is called
_patch_called = False

def get_cache_size():
  return len(_cache)

def getCached(real_func, keys, **kwargs):
  real_keys, multiple = datastore.NormalizeAndTypeCheckKeys(keys)
  if multiple: # give up for now
    return real_func(keys, **kwargs)

  real_key = real_keys[0]
  instance = _cache.get(real_key, None)
  if instance:
    #logging.debug('request_db_cache: Got cached instance of %s (cache size %d)'
    #              % (real_key, len(_cache)))
    return instance  
  model = real_func(keys, **kwargs)
  if model:  
    _cache[real_key] = model  
  #logging.debug('request_db_cache: Cache miss for %s (cache size %d)'
  #              % (real_key, len(_cache)))
  return model

def patch_db_get():
  """Put a request-local cache on db calls"""
  global _patch_called
  # Dan sez: In production, sometimes _patch_called == True.
  # I don't understand why, but skipping this isn't as fatal as asserting it.
  if not _patch_called:
    _patch_called = True
    from functools import partial
    logging.info("called patch_db_get: patched")
    # This patch only works in production?  I don't see the same Gets in development.
    db.get = partial(getCached, db.get)
    # TODO(dan): I think we should also patch db.put to clear the cache for the
    # given object so we protect ourselves against get+put+get.
  else:
    logging.info("called patch_db_get: skipped")
