import urllib2
import logging

from django.utils import simplejson as json
from django.core.management.base import BaseCommand

BASE_URL = 'http://localhost:8080'

class _Task(object):
  def __init__(self, base_url, task_as_json):
    self._obj = json.loads(task_as_json)
    self.name      = self._obj['name']
    self.url       = base_url + self._obj['url']
    self.headers   = dict([(pair[0], pair[1]) for pair in self._obj['headers']])
    self.body      = self._obj['body']
    self.method    = self._obj['method'] # TODO(max): adjust call based on this
    self.eta       = self._obj['eta']
    self.eta_delta = self._obj['eta_delta']

  def __repr__(self):
    return "<Task %s>" % self.name


def run():
  url = BASE_URL + '/dev/run-tasks'
  logging.info(url)
  result = urllib2.urlopen(url).read()
  did_find_tasks = (len(result) > 1)
  if did_find_tasks:
    tasks_as_json = result.split("\n")
    for t_json in tasks_as_json:
      task = _Task(BASE_URL, t_json)
      print "Running %s" % task
      req = urllib2.Request(task.url, task.body, task.headers)
      urllib2.urlopen(req)
  return did_find_tasks

# TODO(dan): Factor out --app-id, --host, --remote, etc..
class Command(BaseCommand):

  def handle(self, *app_labels, **options):
    # Turn off copious DEBUG logging
    logging.getLogger().setLevel(logging.INFO)

    run()
