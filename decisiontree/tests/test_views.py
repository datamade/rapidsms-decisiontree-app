from model_mommy import mommy

from django.core.urlresolvers import reverse

from decisiontree.multitenancy import models as link_models

from .. import models
from .cases import DecisionTreeTestCase, DeleteViewTestMixin


class TestAnswerDelete(DeleteViewTestMixin, DecisionTreeTestCase):
    link_model = link_models.AnswerLink
    model = models.Answer
    success_url_name = 'answer_list'
    url_name = 'delete_answer'


class TestPathDelete(DeleteViewTestMixin, DecisionTreeTestCase):
    link_model = link_models.TransitionLink
    model = models.Transition
    success_url_name = 'path_list'
    url_name = 'delete_path'


class TestMessageDelete(DeleteViewTestMixin, DecisionTreeTestCase):
    link_model = link_models.MessageLink
    model = models.Message
    success_url_name = 'list-messages'
    url_name = 'delete_message'


class TestStateDelete(DeleteViewTestMixin, DecisionTreeTestCase):
    link_model = link_models.TreeStateLink
    model = models.TreeState
    success_url_name = 'state_list'
    url_name = 'delete_state'


class TestSurveyDelete(DeleteViewTestMixin, DecisionTreeTestCase):
    link_model = link_models.TreeLink
    model = models.Tree
    success_url_name = 'list-surveys'
    url_name = 'delete_tree'


class TestTagDelete(DeleteViewTestMixin, DecisionTreeTestCase):
    link_model = link_models.TagLink
    model = models.Tag
    success_url_name = 'list-tags'
    url_name = 'delete-tag'


class TestSurveySessionClose(DecisionTreeTestCase):
    url_name = 'session_close'

    def setUp(self):
        super(TestSurveySessionClose, self).setUp()
        self.user = mommy.make('auth.User', is_superuser=True)
        self.make_tenant_manager(self.user)
        self.login_user(self.user)

        self.session = mommy.make('decisiontree.Session',
                                  state=mommy.make('decisiontree.TreeState'),
                                  connection=self.connection)

    def get_url(self, **kwargs):
        kwargs.setdefault('group_slug', self.tenant.group.slug)
        kwargs.setdefault('tenant_slug', self.tenant.slug)
        kwargs.setdefault('pk', self.session.pk)
        return reverse(self.url_name, kwargs=kwargs)

    def test_get(self):
        """Session close view requires POST."""
        response = self.client.get(self.get_url())
        self.assertEqual(response.status_code, 405)
        self.session = models.Session.objects.get(pk=self.session.pk)
        self.assertTrue(self.session.is_open())
        self.assertFalse(self.session.is_closed())

    def test_delete(self):
        """Session close view requires POST."""
        response = self.client.delete(self.get_url())
        self.assertEqual(response.status_code, 405)
        self.session = models.Session.objects.get(pk=self.session.pk)
        self.assertTrue(self.session.is_open())
        self.assertFalse(self.session.is_closed())

    def test_non_existant(self):
        """View should return 404 response if session does not exist."""
        response = self.client.post(self.get_url(pk=1234))
        self.assertEqual(response.status_code, 404)
        self.session = models.Session.objects.get(pk=self.session.pk)
        self.assertTrue(self.session.is_open())
        self.assertFalse(self.session.is_closed())

    def test_already_closed(self):
        """Session close view does not act on closed session."""
        # TODO: mock to ensure that save is not called.
        self.session.close()
        response = self.client.post(self.get_url())
        expected_url = reverse('recent_sessions', kwargs={
            'group_slug': self.tenant.group.slug,
            'tenant_slug': self.tenant.slug,
            'pk': self.session.tree.pk,
        })
        self.assertRedirectsNoFollow(response, expected_url)
        self.session = models.Session.objects.get(pk=self.session.pk)
        self.assertTrue(self.session.is_closed())
        self.assertFalse(self.session.is_open())

    def test_close(self):
        """Session close view cancels the session."""
        response = self.client.post(self.get_url())
        expected_url = reverse('recent_sessions', kwargs={
            'group_slug': self.tenant.group.slug,
            'tenant_slug': self.tenant.slug,
            'pk': self.session.tree.pk,
        })
        self.assertRedirectsNoFollow(response, expected_url)
        self.session = models.Session.objects.get(pk=self.session.pk)
        self.assertTrue(self.session.is_closed())
        self.assertFalse(self.session.is_open())
