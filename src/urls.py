# -*- coding: utf-8 -*-
from django.conf.urls.defaults import *
from ragendja.urlsauto import urlpatterns
from ragendja.auth.urls import urlpatterns as auth_patterns
#from myapp.forms import UserRegistrationForm
from django.contrib import admin

admin.autodiscover()

handler500 = 'ragendja.views.server_error'
simple_view = 'django.views.generic.simple.direct_to_template'

urlpatterns = auth_patterns + patterns('',
  ('^admin/(.*)', admin.site.root),

  # ability to set language, see http://docs.djangoproject.com/en/1.0/topics/i18n/#the-set-language-redirect-view
  # This requires language to come in on a POST
  (r'^i18n/', include('django.conf.urls.i18n')),

  # direct to template
  url(r'^about$',   simple_view, {'template': 'about.html'},   name='about'),
  url(r'^privacy$', simple_view, {'template': 'privacy.html'}, name='privacy'),
  url(r'^tos$',     simple_view, {'template': 'tos.html'},     name='tos'),
  url(r'^thanks$',  simple_view, {'template': 'thanks.html'},  name='thanks'),

  url(r'^org-required$', simple_view,
      {'template': 'org_required.html'},   name='org-required'),
  url(r'^org-must-match$', simple_view,
      {'template': 'org_must_match.html'},   name='org-must-match'),

  # healthdb urls
  url(r'', include('healthdb.urls')),
  
) + urlpatterns
