# AppEngine imports
from google.appengine.ext import db

# Django imports
from django.contrib.sites.models import Site

# Python
#import logging
import random
import math
import csv

# Local imports
import models

# skip: il1o0, uppercase
_rchars = "abcdefghjkmnpqrstuvwxyz23456789"

# Return NaN in a portable way for Python 2.5.
# float('NaN') doesn't work until Python 2.6.
# See http://www.gossamer-threads.com/lists/python/python/656960
NaN = 1e1000 / 1e1000

def assertNear(self, doub1, doub2, eps):
  self.assertTrue(abs(doub1 - doub2) <= eps)
  
def assertIsNanOrNear(self, doub1, doub2, eps):
  self.assertTrue(isNanOrNear(doub1, doub2, eps), 
                  ("doub1: %s, doub2: %s, abs(doub1 - doub2): %s, eps: %s" %
                   (doub1, doub2, abs(doub1-doub2), eps)))
  
def isNanOrNear(doub1, doub2, eps):
  nanOrNear = (isNaN(doub1) and isNaN(doub2)) or (abs(doub1 - doub2) <= eps)
  return nanOrNear

def printable_properties(model_class):
  '''Return properties we know how to print.'''
  properties = model_class.properties()
  props = {}
  for name in properties:
    thing = properties[name]
    if (isinstance(thing, db.IntegerProperty) or
        isinstance(thing, db.FloatProperty) or
        isinstance(thing, db.StringProperty) or
        isinstance(thing, db.DateProperty) or
        isinstance(thing, db.DateTimeProperty) or
        isinstance(thing, db.TextProperty) or
        isinstance(thing, models.ZscoreAndPercentileProperty)):
      props[name] = thing
    else:
      pass
      #logging.info("Reject %s" % properties[name])
  return props


class StringWriter(object):
  '''Class with a write() method that appends to a str'''
  def __init__(self):
    self.str = ''

  def write(self, a_str):
    import logging
    self.str += a_str

  def get_str(self):
    return self.str

def _csv_string(a_val):
  '''Return a string encoded for a csvwriter.
  They don't handle unicode, so encode in utf-8.
  Set None to empty string.
  '''
  if a_val is None: a_val = ''
  else:
    a_val = '%s' % a_val
    a_val = a_val.encode('utf-8')
  return a_val

def csv_line(prop_names, props, model_class):
  '''Return a CSV line with the properties of the given model_class.

  A CSV line comes from a csv.writer.  \r and \n are quoted, but line
  unterminated.

  Print any property returned from prop_names.
  '''
  vals = []
  for name in prop_names:
    val = getattr(model_class, name)
    if isinstance(props[name], models.ZscoreAndPercentileProperty):
      # TODO(dan): Remove this hack
      if val:
        vals.extend([val.zscore, val.percentile])
      else:
        vals.extend([None, None])
# Doesn't work, don't know why
#    elif isinstance(props[name], db.FloatProperty) and isNaN(float(val)):
#      val = "?"
    else:
      vals.append(val)

  string_writer = StringWriter()
  # leave lineterminator \r\n so that those chars will be quoted
  cwriter = csv.writer(string_writer)
  cwriter.writerow(map(_csv_string, vals))
  the_str = string_writer.get_str()
  # remove final \r\n
  return the_str[0:(len(the_str)-2)]


def random_string(len):
  """Generate a user-friendly random string of the given length."""
  rstr = ''
  for dummy in range(len):
      rstr += random.choice(_rchars)
  return rstr

def get_domain():
  return 'http://%s' % Site.objects.get_current().domain # django caches this

def isNaN(num):
  """Return True iff num is a float nan"""
  # This is absurd, but Python 2.5.2 on Windows XP does not allow float("nan")!
  return isinstance(num, float) and (num != num)

def isNaNString(numstr):
  """Return true if str is a string whose lower() is 'nan' or '-1.#ind'

  On Windows it might be nan, on Linux -1.#ind.
  """
  return ((isinstance(numstr, str)
           and ((numstr.lower() == 'nan') or (numstr.lower() == '-1.#ind')))
          or (isinstance(numstr, unicode)
           and ((numstr.lower() == u'nan') or (numstr.lower() == u'-1.#ind'))))

def bucket_zscore(val):
  """Put val into a bucket of width 1, return left edge.
  Return NaN if we can't take floor.

   0.1 =>  0.0 to  1.0
   0.6 =>  0.0 to  1.0
  -0.1 => -1.0 to  0.0
  -0.6 => -1.0 to -0.0
"""
  ret = NaN
  try:
    ret = math.floor(val)
  except TypeError, err:
    pass
  return ret

def string_eq_nocase(str1, str2):
  '''Compare two strings and return true if they are equal or None (case ignored)
  '''
  if (str2 == ''):
    return True
  elif ((str1 is None) and (str2 is None)):
    return True
  elif ((str1 is None) or (str2 is None)):
    return False
  elif ((str1 is not None) and (str2 is not None)):
    if (str1.lower() == str2.lower()):
      return True

  return False
