# Copyright 2008 Jens Scheffler
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Based on http://appengine-cookbook.appspot.com/recipe/collect-profiling-data-for-any-datastore-operation

from google.appengine.api import apiproxy_stub_map
from google.appengine.api import memcache
from google.appengine.datastore import datastore_index
import logging
import operator
import datetime

_requestmap = {}
_call_num = 0
_post_call_num = 0
_callmap = {}

# True iff patch_appengine() is called
_patch_called = False

def log_callmap():
  global _callmap
  for call in _callmap:
    logging.debug('DB_LOG: Got %s %d times' % (call, _callmap[call]))

def clear_callmap():
  global _callmap
  _callmap = {}

def clear_requestmap():
  global _requestmap
  _requestmap = {}

def db_log(model, call, details=''):
  """Call this method whenever the database is invoked.
  
  Args:
    model: the model name (aka kind) that the operation is on
    call: the kind of operation (Get/Put/...)
    details: any text that should be added to the detailed log entry.
  """
  
  # First, let's update memcache
#  if model:
#    stats = memcache.get('DB_TMP_STATS')
#    if stats is None: stats = {}
#    key = '%s_%s' % (call, model)
#    stats[key] = stats.get(key, 0) + 1
#    memcache.set('DB_TMP_STATS', stats)
  
  # Next, let's log for some more detailed analysis
  logging.debug('DB_LOG: %s @ %s (%s)', call, model, details)


def patch_appengine():
  def name_from_elem(elem):
    return "%s:%s" % (elem.type(), elem.id()) 

  """Apply a hook to app engine that logs db statistics."""
  def model_name_from_key(key):
    elem_list = key.path().element_list()
    a_name = name_from_elem(elem_list[0])
    if len(elem_list) > 1:
      a_name += " " + name_from_elem(elem_list[1])
    return a_name

  def prehook(service, call, request, response):
    global _call_num, _callmap, _requestmap

    a_key = "%s:%s" % (call, request)
    _requestmap[a_key] = (datetime.datetime.now(), _call_num)
    _call_num += 1

    if call not in _callmap:
      _callmap[call]  = 0
    _callmap[call] += 1
    loghook(service, call, request, response)

  def delta_to_ms(delta):
    return (delta.microseconds / 1000.0 + delta.seconds * 1000
      + delta.days * 24 * 60 * 60 * 1000)

  def posthook(service, call, request, response):
    global _post_call_num

    a_key = "%s:%s" % (call, request)
    (time1, _call_num) = _requestmap[a_key]
    delta = datetime.datetime.now() - time1
    a_key_no_newlines = a_key.replace("\n", " ")
    logging.debug("DB_LOG: call %4d time %6d ms, request %s" %
                  (_call_num, delta_to_ms(delta), a_key_no_newlines))
    _post_call_num += 1

  def loghook(service, call, request, response):
#    logging.debug("service %s, call %s, request %s, response %s"
#                 % (service, call, request, response))
    assert service == 'datastore_v3'
    if call == 'Put':
      for entity in request.entity_list():
        db_log(model_name_from_key(entity.key()), call)
    elif call in ('Get', 'Delete'):
      for key in request.key_list():
        db_log(model_name_from_key(key), call)
    elif call == 'RunQuery':
      kind = datastore_index.CompositeIndexForQuery(request)[1]
      db_log(kind, call)
    else:
      db_log(None, call)

  global _patch_called
  assert not _patch_called
  logging.info("called patch_appengine")
  _patch_called = True
  apiproxy_stub_map.apiproxy.GetPreCallHooks().Append(
      'db_log', prehook, 'datastore_v3')
  apiproxy_stub_map.apiproxy.GetPostCallHooks().Append(
      'db_log', posthook, 'datastore_v3')
