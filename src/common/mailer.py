''' Methods to send emails to users and administrators '''

# python imports
import logging

# google imports
#from google.appengine.ext import deferred

from google.appengine.api.mail import EmailMessage as GoogleEmailMessage

# django imports
from django.template.loader import render_to_string
from django.core import mail
from django.utils.safestring import mark_safe

# AEP imports
from appenginepatcher import on_production_server

# local imports
import settings

def send_mail(subject, body, addresslist, 
              sender = settings.DEFAULT_FROM_EMAIL,
              doAppendSig=True, bcclist = None, reply_to = None):
  """ wrapper for Django's send_mail method """
  # Always prepend prefix to the subject
  subject = ''.join(subject.splitlines()) # *must not* contain newlines
  subject = "%s %s" % (settings.EMAIL_SUBJECT_PREFIX, subject)
  body = unicode(body) # may come in as a django.utils.safestring.SafeUnicode

  # Always include a signature
  if doAppendSig:
    body = "%s\n%s" % (body, settings.EMAIL_SIGNATURE)

  logging.debug("mailer.send_mail: addresslist %s bcclist %s body:\n%s" %
                (addresslist, bcclist, body))

  email = GoogleEmailMessage(subject  = subject, 
                             body     = body, 
                             sender   = sender,
                             to       = addresslist)
  if bcclist is not None and len(bcclist) > 0:
    email.bcc = bcclist
  if reply_to is not None:
    email.reply_to = reply_to

  from tasks import deliver_email_task
  # Note: For some reason synchronous works, asynchronous isn't working.
  # I'm not going to worry about that for now.
  # TODO(dan): Fix deferred.defer.
  deliver_email_task(email)
  #deferred.defer(deliver_email_task, email)

  # for testing, appengine patch keeps a list of mails
  if hasattr(mail, 'outbox') and not on_production_server:
    mail.outbox.append(email) #@UndefinedVariable (ignore py checker warnings)

def render_to_string_assume_safe(template, attrs):
  """Mark all attrs string values safe before rendering to disable quoting

  This should only be done if you aren't rendering for HTML or trust the values
  enough that you won't be hacked.

  We currently email text, so there are no possibilities of HTML hacks. 
  """
  new_attrs = {}
  for key in attrs.keys():
    val = attrs[key]
    if isinstance(val, str) or isinstance(val, unicode):
      val = mark_safe(val)
    new_attrs[key] = val
  return render_to_string(template, new_attrs)

def _admin_address_list():
  '''List of email addresses suitable for "to" field.

  See also http://code.google.com/appengine/docs/python/mail/sendingmail.html.
  '''
  return ["%s <%s>" % (admin[0], admin[1]) for admin in settings.ADMINS]

def send_email_to_admins(subject, body):
  """ convenience method to send simple notifications to admins """
  send_mail(subject, body, _admin_address_list(), doAppendSig=False)

def email_contact_us(contacter, text):
  # TODO(dan): contact email has no sig.  Why?
  send_email_to_admins(subject='Contact Us: response from %s' % contacter,
                       body=text)


def email_new_patient(patient):
  org = patient.organization
  send_email_to_admins(subject='%s: New patient: %s'
                       % (org, patient.name),
                       body="Organization: %s\nNew patient: %s"
                       % (org, patient.get_view_fullurl()))

def email_new_visit(visit):
  pat = visit.get_patient()
  org = pat.organization
  send_email_to_admins(subject='%s: New visit for %s'
                       % (org, pat.name),
                       body="Organization: %s\nNew visit: %s"
                       % (org, visit.get_view_fullurl()))

def email_new_patient_with_visit(patient, visit):
  org = patient.organization
  send_email_to_admins(subject='%s: New patient %s with visit %s'
                               % (org, patient.name, visit.short_string),
                       body="Organization: %s\nNew patient: %s\nNew visit: %s"
                               % (org,
                                  patient.get_view_fullurl(),
                                  visit.get_view_fullurl()))

def email_patient_merge(patient_to_keep, patients):
  org = patient_to_keep.organization
  send_email_to_admins(subject='%s: Patient Merge'
                               % (org),
                       body="Organization: %s\nPatient kept: %s\nOut of this list of patients: %s"
                               % (org,
                                  patient_to_keep,
                                  patients))

def email_patient_with_visit_deleted(patient, visits):
  org = patient.organization
  send_email_to_admins(subject='%s: Patient %s with %d visit(s) was deleted'
                               % (org, patient.name, len(visits)),
                       body="Organization: %s\nPatient deleted: %s\nVisit(s) deleted: %s"
                               % (org,
                                  patient,
                                  visits))


def email_visit_deleted(patient, visit):
  org = patient.organization
  send_email_to_admins(subject='%s: A Visit for patient %s was deleted'
                               % (org, patient.name),
                       body="Organization: %s\nVisit(s) deleted: %s"
                               % (org,
                                  visit))
