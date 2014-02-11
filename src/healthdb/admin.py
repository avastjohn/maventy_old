import logging

from django.http import HttpResponse, Http404

def run_tasks(request):
  """ Returns a list of task json which may be fetched by wget to execute
  tasks locally.
  
  @see manage.runtasks
  
  @see http://appengine-cookbook.appspot.com/recipe/automatically-run-tasks-from-task-queue-on-development-sdk/
  """
  import os
  if not os.environ['SERVER_SOFTWARE'].startswith('Development'):
    logging.error("This URL is only valid in a development environment.")
    raise Http404
  else:
    from datetime import datetime
    from google.appengine.api import apiproxy_stub_map
    stub = apiproxy_stub_map.apiproxy.GetStub('taskqueue')
    
    #get all the tasks for all the queues
    tasks = []
    for queue in stub.GetQueues():
      tasks.extend( stub.GetTasks(queue['name']) )
    
    #keep only tasks that need to be executed
    now = datetime.now()
    fn = lambda t: datetime.strptime(t['eta'],'%Y/%m/%d %H:%M:%S') < now
    tasks = filter(fn, tasks)

    from django.utils import simplejson as json
    result = '\n'.join([json.dumps(t) for t in tasks])
    
    #remove tasks from queues
    for queue in stub.GetQueues():
      stub.FlushQueue(queue['name'])
  
    return HttpResponse(result)
