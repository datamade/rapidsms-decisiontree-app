from urlparse import parse_qs, urlparse

from model_mommy import mommy

from rapidsms.tests.harness import MockRouter

from multitenancy.models import TenantRole

from django.conf import settings
from django.contrib.auth import login
from django.core.urlresolvers import reverse_lazy
from django.http import HttpRequest
from django.test import TestCase
from django.utils.encoding import force_text

from decisiontree.app import App as DecisionApp


class DecisionTreeTestCase(TestCase):
    login_url = reverse_lazy('login')

    def setUp(self):
        super(DecisionTreeTestCase, self).setUp()
        self.tenant = mommy.make('multitenancy.Tenant')
        self.backend = mommy.make('rapidsms.Backend')
        self.backend_link = mommy.make('multitenancy.BackendLink',
                                       backend=self.backend, tenant=self.tenant)
        self.contact = mommy.make('rapidsms.Contact')
        self.contact_link = mommy.make('multitenancy.ContactLink',
                                       contact=self.contact, tenant=self.tenant)
        self.connection = mommy.make('rapidsms.Connection',
                                     contact=self.contact, backend=self.backend,
                                     identity='1112223333')
        self.router = MockRouter()
        self.app = DecisionApp(router=self.router)

    def assertRedirectsNoFollow(self, response, expected_url, use_params=True,
                                status_code=302):
        """Checks response redirect without loading the destination page.
        Django's assertRedirects method loads the destination page, which
        requires that the page be renderable in the current test context
        (possibly requiring additional, unrelated setup).
        """
        # Assert that the response has the correct redirect code.
        self.assertEqual(
            response.status_code, status_code,
            "Response didn't redirect as expected: Response code was {0} "
            "(expected {1})".format(
                response.status_code, status_code,
            ),
        )

        # Assert that the response redirects to the correct base URL.
        # Use force_text to force evaluation of anything created by
        # reverse_lazy.
        response_url = force_text(response['location'])
        expected_url = force_text(expected_url)
        parsed1 = urlparse(response_url)
        parsed2 = urlparse(expected_url)
        self.assertEqual(
            parsed1.path, parsed2.path,
            "Response did not redirect to the expected URL: Redirect "
            "location was {0} (expected {1})".format(
                parsed1.path, parsed2.path,
            ),
        )

        # Optionally assert that the response redirect URL has the correct
        # GET parameters.
        if use_params:
            self.assertDictEqual(
                parse_qs(parsed1.query), parse_qs(parsed2.query),
                "Response did not have the GET parameters expected: GET "
                "parameters were {0} (expected {1})".format(
                    parsed1.query or {}, parsed2.query or {},
                ),
            )

    def assertRedirectsToLogin(self, response, login_url=None,
                               use_params=False, status_code=302):
        login_url = login_url or self.login_url
        return self.assertRedirectsNoFollow(response, login_url, use_params,
                                            status_code)

    def login_user(self, user):
        """Log in a user without need for a password.
        Adapted from
        http://jameswestby.net/weblog/tech/17-directly-logging-in-a-user-in-django-tests.html
        """
        user.backend = 'django.contrib.auth.backends.ModelBackend'
        engine = __import__(settings.SESSION_ENGINE, fromlist=['SessionStore'])

        # Create a fake request to store login details.
        request = HttpRequest()
        request.session = self.client.session or engine.SessionStore()
        login(request, user)

        # Set the cookie to represent the session.
        session_cookie = settings.SESSION_COOKIE_NAME
        self.client.cookies[session_cookie] = request.session.session_key
        self.client.cookies[session_cookie].update({
            'max-age': None,
            'path': '/',
            'domain': settings.SESSION_COOKIE_DOMAIN,
            'secure': settings.SESSION_COOKIE_SECURE or None,
            'expires': None,
        })

        # Save the session values.
        request.session.save()

        return user

    def make_group_manager(self, user, group=None):
        if group is None:
            group = self.tenant.group
        mommy.make('multitenancy.TenantRole',
                   group=group,
                   role=TenantRole.ROLE_GROUP_MANAGER)

    def make_tenant_manager(self, user, tenant=None):
        if tenant is None:
            tenant = self.tenant
        mommy.make('multitenancy.TenantRole',
                   group=tenant.group, tenant=tenant, user=user,
                   role=TenantRole.ROLE_TENANT_MANAGER)
