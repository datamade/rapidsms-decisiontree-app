"""Common logic for CRUD views used in rapidsms-decisiontree."""

from django.contrib import messages
from django.contrib.admin.utils import NestedObjects
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ImproperlyConfigured
from django.core.urlresolvers import reverse
from django.db import transaction, DEFAULT_DB_ALIAS
from django.utils.decorators import method_decorator
from django.views.generic import DeleteView, DetailView, ListView, UpdateView
from django.views.generic.detail import SingleObjectTemplateResponseMixin
from django.views.generic.edit import ModelFormMixin, ProcessFormView

from decisiontree.multitenancy.views import TenantViewMixin
from decisiontree.multitenancy.utils import multitenancy_enabled


def cbv_decorator(function_decorator):
    """Allows a function-based decorator to be used on a class-based View."""

    def class_decorator(View):
        View.dispatch = method_decorator(function_decorator)(View.dispatch)
        return View
    return class_decorator


class CancellationMixin(object):
    """Specify a URL to go to if the user cancels their action."""
    cancellation_url_name = None

    def get_cancellation_url(self, *args, **kwargs):
        """Which URL to go to if the user cancels their action."""
        if self.cancellation_url_name:
            return reverse(self.cancellation_url_name, args=args, kwargs=kwargs)
        raise ImproperlyConfigured("No cancellation URL known. Provide a "
                                   "cancellation_url_name.")

    def get_context_data(self, **kwargs):
        kwargs.setdefault('cancellation_url', self.get_cancellation_url())
        return super(CancellationMixin, self).get_context_data(**kwargs)


class SuccessMessageMixin(object):
    """Add a user message when an action is successfully completed."""
    success_message = None
    success_message_level = messages.INFO

    def get_success_message(self):
        if self.success_message:
            return self.success_message.format(obj=self.object)
        return None

    def get_success_url(self, *args, **kwargs):
        message = self.get_success_message()
        if message:
            messages.add_message(self.request, self.success_message_level, message)
        return super(SuccessMessageMixin, self).get_success_url(*args, **kwargs)


@cbv_decorator(login_required)
class TreeListView(TenantViewMixin, ListView):
    create_url_name = None
    limit = None
    order_by = None
    select_related = None
    template_name = "tree/cbv/list.html"

    def get_create_url(self):
        if self.create_url_name:
            if multitenancy_enabled():
                return reverse(self.create_url_name, kwargs={
                    'group_slug': self.group.slug,
                    'tenant_slug': self.tenant.slug,
                })
            return reverse(self.create_url_name)
        return None

    def get_queryset(self):
        qs = super(TreeListView, self).get_queryset()
        if self.select_related is not None:
            qs = qs.select_related(*self.select_related)
        if self.order_by is not None:
            qs = qs.order_by(*self.order_by)
        if self.limit is not None:
            qs = qs[:self.limit]
        return qs


@cbv_decorator(login_required)
class TreeDetailView(TenantViewMixin, DetailView):
    pass


@cbv_decorator(login_required)
@cbv_decorator(transaction.atomic)
class TreeUpdateView(SuccessMessageMixin, TenantViewMixin, CancellationMixin,
                     UpdateView):
    template_name = "tree/cbv/create_update.html"


@cbv_decorator(login_required)
@cbv_decorator(transaction.atomic)
class TreeCreateUpdateView(SuccessMessageMixin, TenantViewMixin,
                           CancellationMixin, SingleObjectTemplateResponseMixin,
                           ModelFormMixin, ProcessFormView):
    """Combines logic for UpdateView and CreateView."""
    CREATE_MODE = 'create'
    UPDATE_MODE = 'edit'

    create_success_message = None
    edit_success_message = None
    template_suffix_name = "_form"
    template_name = "tree/cbv/create_update.html"

    def get(self, request, *args, **kwargs):
        self.set_object(request, *args, **kwargs)
        return super(TreeCreateUpdateView, self).get(request, *args, **kwargs)

    def get_success_message(self):
        if self.mode == self.UPDATE_MODE and self.edit_success_message:
            return self.edit_success_message.format(obj=self.object)
        elif self.mode == self.CREATE_MODE and self.create_success_message:
            return self.create_success_message.format(obj=self.object)
        return None

    def post(self, request, *args, **kwargs):
        self.set_object(request, *args, **kwargs)
        return super(TreeCreateUpdateView, self).post(request, *args, **kwargs)

    def set_object(self, request, *args, **kwargs):
        if kwargs.get(self.pk_url_kwarg) or kwargs.get(self.slug_url_kwarg):
            self.mode = self.UPDATE_MODE
            self.object = self.get_object()
        else:
            self.mode = self.CREATE_MODE
            self.object = None


@cbv_decorator(login_required)
@cbv_decorator(transaction.atomic)
class TreeDeleteView(SuccessMessageMixin, TenantViewMixin, CancellationMixin,
                     DeleteView):
    template_name = "tree/cbv/delete.html"

    def get_context_data(self, **kwargs):
        collector = NestedObjects(using=DEFAULT_DB_ALIAS)
        collector.collect([self.object])
        kwargs.setdefault('nested_objects', collector.nested())
        return super(TreeDeleteView, self).get_context_data(**kwargs)
