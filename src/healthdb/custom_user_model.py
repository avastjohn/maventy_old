# See http://code.google.com/p/app-engine-patch/wiki/CustomUserModel

from google.appengine.ext import db
from ragendja.auth.models import User as Ruser
import models

class User(Ruser):
  """A custom user object"""
  default_country = db.StringProperty(required = False,
                      choices = models.Patient.country.choices)

  # TODO(dan): Make required = True if and when all old users have one
  organization = db.StringProperty(required = False, default = '')
