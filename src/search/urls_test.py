# -*- coding: utf-8 -*-
from django.conf.urls.defaults import *

urlpatterns = patterns('search.tests',
    ('^search$', 'search_test'),
    ('^live-search$', 'live_search_test'),
) + patterns('search.views',
    (r'^bg-tasks/search/update_values_index/$', 'update_values_index'),
    (r'^bg-tasks/search/update_relation_index/$', 'update_relation_index'),
)
