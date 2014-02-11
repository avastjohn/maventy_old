"""Background tasks. References to Django not permitted (yet).

see http://code.google.com/appengine/articles/deferred.html
see http://code.google.com/appengine/docs/python/taskqueue/
"""

# Python imports
import logging

# Google imports
from google.appengine.runtime.apiproxy_errors \
  import OverQuotaError, DeadlineExceededError
from google.appengine.api import mail

# Django imports ARE NOT ALLOWED until path issues are fixed


def deliver_email_task(emailMessage):
  """Invoke the send() method on the google EmailMessage, catch errors.
  
  This method should be invoked asynchronously, through the "deferred" call.
  Google claims that "it'll automatically retry in the event of timeouts 
    and other transient errors".
  
  see http://code.google.com/appengine/articles/deferred.html
  see http://code.google.com/appengine/docs/python/taskqueue/
  """
  try:
    emailMessage.send()
    logging.info("Sending email succeeded (subject: %s, to: %s)" %
                 (emailMessage.subject, emailMessage.to))
  except OverQuotaError:
    logging.error("Sending email failed - OverQuotaError")
    raise
  except DeadlineExceededError:
    logging.error("Sending email failed - DeadlineExceededError")
    raise
  except Exception:
    logging.error("Sending email failed")
    raise
