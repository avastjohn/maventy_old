# -*- coding: utf-8 -*-
from ragendja.settings_pre import *

# Settings that we don't check in
import unsaved_settings

# Increase this when you update your media on the production site, so users
# don't have to refresh their cache. By setting this your MEDIA_URL
# automatically becomes /media/MEDIA_VERSION/
MEDIA_VERSION = 1

# By hosting media on a different domain we can get a speedup (more parallel
# browser connections).
#if on_production_server or not have_appserver:
#  MEDIA_URL = 'http://media.mydomain.com/media/%d/'

# do not prefix model names with application names and _
DJANGO_STYLE_MODEL_KIND = False

# TODO(max): look for ways to set this to 'America/Chicago' without
#   breaking the comparison between datetime.now() and datastore's now().
TIME_ZONE = 'GMT'

# Add base media (jquery can be easily added via INSTALLED_APPS)
COMBINE_MEDIA = {
  'combined-%(LANGUAGE_CODE)s.js': (
    # See documentation why site_data can be useful:
    # http://code.google.com/p/app-engine-patch/wiki/MediaGenerator
    '.site_data.js',
  ),
  'combined-%(LANGUAGE_DIR)s.css': (
    'global/look.css',
  ),
}

# Django setting for email addresses of site admins
# http://docs.djangoproject.com/en/1.0/topics/email/#mail-admins
# http://docs.djangoproject.com/en/dev/howto/error-reporting/#error-reporting-via-e-mail
# Note: if there is 1 tuple, the last comma is necessary!
ADMINS = (('childhealth Administrators', 'childhealth-admin@maventy.org'),)
# Django setting for email prefix
EMAIL_SUBJECT_PREFIX = '[childhealth] '
EMAIL_SIGNATURE = 'Maventy.org child health system'
# Send emails on 404s that have referers.
SEND_BROKEN_LINK_EMAILS = True

if on_production_server:
  # http://code.google.com/appengine/docs/python/mail/sendingmail.html
  # "The sender address can be either the email address of a registered
  # administrator for the application, or the email address of the current
  # signed-in user (the user making the request that is sending the message)."
  DEFAULT_FROM_EMAIL = 'dan@maventy.org'
  SERVER_EMAIL = DEFAULT_FROM_EMAIL
  TEMPLATE_STRING_IF_INVALID = ""
else:
  TEMPLATE_STRING_IF_INVALID = "[[ UNDEFINED VARIABLE ]]"

FILE_UPLOAD_MAX_MEMORY_SIZE = 1048576  # 1 MB

#ENABLE_PROFILER = True
#ONLY_FORCED_PROFILE = True
#PROFILE_PERCENTAGE = 25
#SORT_PROFILE_RESULTS_BY = 'cumulative' # default is 'time'
# Profile only datastore calls
#PROFILE_PATTERN = 'ext.db..+\((?:get|get_by_key_name|fetch|count|put)\)'

# Enable I18N
# Default is True.
# USE_I18N = True

# Force language to 'en' (English).
# Leave this commented out, or a browser requesting French will get English.
#LANGUAGE_CODE = 'en'

# Restrict supported languages (and JS media generation)
# See http://docs.djangoproject.com/en/1.0/ref/settings/#languages
# TODO(dan): Generate .po-s from settings.py.
gettext = lambda s: s
LANGUAGES = (
  # Putting the direct translation here without gettext() means the translated
  # name shows up in the languages selection no matter what language we're in
  ('en', 'English'),
  ('fr', 'Française'),
)

TEMPLATE_CONTEXT_PROCESSORS = (
  'django.core.context_processors.auth',
  'django.core.context_processors.media',
  'django.core.context_processors.request',
  'django.core.context_processors.i18n',
  'healthdb.context_processors.vars',
)

MIDDLEWARE_CLASSES = (
  'ragendja.middleware.ErrorMiddleware',
  'django.contrib.sessions.middleware.SessionMiddleware',
  # i18n
  'django.middleware.locale.LocaleMiddleware',
  # Django authentication
  'django.contrib.auth.middleware.AuthenticationMiddleware',

  # LoginRequiredMiddleware allows us to use LOGIN_REQUIRED_PREFIXES
  #'ragendja.middleware.LoginRequiredMiddleware',

  # Google authentication
  #'ragendja.auth.middleware.GoogleAuthenticationMiddleware',
  # Hybrid Django/Google authentication
  #'ragendja.auth.middleware.HybridAuthenticationMiddleware',
  'django.middleware.common.CommonMiddleware',
  'ragendja.sites.dynamicsite.DynamicSiteIDMiddleware',
  'django.contrib.flatpages.middleware.FlatpageFallbackMiddleware',
  'django.contrib.redirects.middleware.RedirectFallbackMiddleware',
)

# Google authentication
#AUTH_USER_MODULE = 'ragendja.auth.google_models'
#AUTH_ADMIN_MODULE = 'ragendja.auth.google_admin'
# Hybrid Django/Google authentication
#AUTH_USER_MODULE = 'ragendja.auth.hybrid_models'
# Custom user model:
AUTH_USER_MODULE = 'healthdb.custom_user_model'

LOGIN_URL = '/account/login/'
LOGOUT_URL = '/account/logout/'
LOGIN_REDIRECT_URL = '/'

#LOGIN_REQUIRED_PREFIXES = (
#)

# NO_LOGIN_REQUIRED_PREFIXES overrides LOGIN_REQUIRED_PREFIXES
# See http://code.google.com/p/app-engine-patch/wiki/RagendjaAuth
#NO_LOGIN_REQUIRED_PREFIXES = (
#)

INSTALLED_APPS = (
  'django.contrib.auth',
  'django.contrib.sessions',
  'django.contrib.admin',
  'django.contrib.webdesign',
  'django.contrib.flatpages',
  'django.contrib.redirects',
  'django.contrib.sites',
  'appenginepatcher',
  'ragendja',
  'healthdb',
  'registration',
  'search',
#  'mediautils',
)

# List apps which should be left out from app settings and urlsauto loading
IGNORE_APP_SETTINGS = IGNORE_APP_URLSAUTO = (
  # Example:
  # 'django.contrib.admin',
  # 'django.contrib.auth',
  # 'yetanotherapp',
  'healthdb',
)

# Remote access to production server (e.g., via manage.py shell --remote)
DATABASE_OPTIONS = {
  # Override remoteapi handler's path (default: '/remote_api').
  # This is a good idea, so you make it not too easy for hackers. ;)
  # Don't forget to also update your app.yaml!
  'remote_url': '/remote-api-34358334',

  # !!!Normally, the following settings should not be used!!!

  # Always use remoteapi (no need to add manage.py --remote option)
  #'use_remote': True,

  # Change appid for remote connection (by default it's the same as in
  # your app.yaml)
  #'remote_id': 'otherappid',

  # Change domain (default: <remoteid>.appspot.com)
  #'remote_host': 'bla.com',
}

from ragendja.settings_post import *

# Set DEBUG = False to test 404.html and 500.html in development
# DEBUG = False

RECAPTCHA_PUBLIC_KEY = '6Le8qwgAAAAAAFTckJQI1ucaGJ_DDfuY4XUgJotb'
RECAPTCHA_PRIVATE_KEY = unsaved_settings.RECAPTCHA_PRIVATE_KEY
