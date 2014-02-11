"""
>>> from django.contrib.sites.models import Site
>>> from django.conf import settings
>>> old_SITE_ID = getattr(settings, 'SITE_ID', None)
>>> site = Site(domain="example.com", name="example.com")
>>> site.save()
>>> settings.SITE_ID = str(site.key())

>>> # Make sure that get_current() does not return a deleted Site object.
>>> s = Site.objects.get_current()
>>> isinstance(s, Site)
True

>>> s.delete()
>>> Site.objects.get_current()

>>> settings.SITE_ID = old_SITE_ID
"""
