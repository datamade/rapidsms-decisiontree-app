from multitenancy.models import TenantEnabled

from django.db import models
from django.utils.encoding import python_2_unicode_compatible


@python_2_unicode_compatible
class TenantLink(TenantEnabled):
    # Whether the linked object's relationship to a tenant is direct or
    # derived. Derived relationships are handled by the signals in
    # decisiontree/multitenancy/signals.py.
    direct = True

    class Meta:
        abstract = True

    def __str__(self):
        return self.linked.__str__()


class AnswerLink(TenantLink):
    linked = models.OneToOneField('decisiontree.Answer', related_name='tenantlink')


class EntryLink(TenantLink):
    direct = False
    linked = models.OneToOneField('decisiontree.Entry', related_name='tenantlink')


class MessageLink(TenantLink):
    linked = models.OneToOneField('decisiontree.Message', related_name='tenantlink')


class SessionLink(TenantLink):
    direct = False
    linked = models.OneToOneField('decisiontree.Session', related_name='tenantlink')


class TagLink(TenantLink):
    linked = models.OneToOneField('decisiontree.Tag', related_name='tenantlink')


class TagNotificationLink(TenantLink):
    direct = False
    linked = models.OneToOneField('decisiontree.TagNotification', related_name='tenantlink')


class TransitionLink(TenantLink):
    linked = models.OneToOneField('decisiontree.Transition', related_name='tenantlink')


class TreeLink(TenantLink):
    linked = models.OneToOneField('decisiontree.Tree', related_name='tenantlink')


class TreeStateLink(TenantLink):
    linked = models.OneToOneField('decisiontree.TreeState', related_name='tenantlink')
