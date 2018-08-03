import csv
from io import StringIO

from django.db.models import Count
from django.http import HttpResponse
from django.shortcuts import redirect
# from django.utils.datastructures import SortedDict
from collections import OrderedDict

from .. import forms
from .. import models
from . import base


class AnswerList(base.TreeListView):
    create_url_name = 'add_answer'
    model = models.Answer
    order_by = ['name']
    template_name = 'tree/answers/list.html'


class AnswerCreateUpdate(base.TreeCreateUpdateView):
    cancellation_url_name = 'answer_list'
    create_success_message = "You have successfully inserted Answer {obj.answer}"
    edit_success_message = "You have successfully updated the Answer"
    form_class = forms.AnswerCreateUpdateForm
    model = models.Answer
    success_url_name = 'answer_list'


class AnswerDelete(base.TreeDeleteView):
    cancellation_url_name = 'answer_list'
    model = models.Answer
    success_message = "Answer successfully deleted"
    success_url_name = 'answer_list'


class EntryList(base.TreeListView):
    limit = 25
    model = models.Entry
    order_by = ['-time']
    select_related = []
    template_name = 'tree/entries/list.html'


class EntryUpdate(base.TreeUpdateView):
    cancellation_url_name = 'survey-report'
    model = models.Entry
    form_class = forms.EntryTagForm
    success_message = "Tags successfully updated"
    success_url_name = 'survey-report'

    def get_cancellation_url(self):
        pk = self.object.session.tree.pk
        return super(EntryUpdate, self).get_cancellation_url(pk=pk)

    def get_success_url(self):
        pk = self.object.session.tree.pk
        return super(EntryUpdate, self).get_success_url(pk=pk)


class PathList(base.TreeListView):
    create_url_name = 'add_path'
    model = models.Transition
    order_by = ['current_state__question__text']
    select_related = ['current_state__question', 'next_state__question', 'answer', 'tags']
    template_name = "tree/paths/list.html"


class PathCreateUpdate(base.TreeCreateUpdateView):
    cancellation_url_name = 'path_list'
    create_success_message = "You have successfully inserted Question Path {obj.id}"
    edit_success_message = "Path successfully updated"
    form_class = forms.PathCreateUpdateForm
    model = models.Transition
    success_url_name = 'path_list'


class PathDelete(base.TreeDeleteView):
    cancellation_url_name = 'path_list'
    model = models.Transition
    success_message = "Path successfully deleted"
    success_url_name = 'path_list'


class QuestionList(base.TreeListView):
    create_url_name = 'add_question'
    model = models.Question
    order_by = ['text']
    template_name = 'tree/questions/list.html'


class QuestionCreateUpdate(base.TreeCreateUpdateView):
    cancellation_url_name = 'list-questions'
    create_success_message = "You have successfully inserted a Question {obj.text}"
    edit_success_message = "You have successfully updated the Question"
    form_class = forms.QuestionCreateUpdateForm
    model = models.Question
    success_url_name = 'list-questions'
    template_name = "tree/questions/create_update.html"


class QuestionDelete(base.TreeDeleteView):
    cancellation_url_name = 'list-questions'
    model = models.Question
    success_message = "Question successfully deleted"
    success_url_name = 'list-questions'


class StateList(base.TreeListView):
    create_url_name = 'add_state'
    model = models.TreeState
    order_by = ['question']
    select_related = ['question']
    template_name = "tree/states/list.html"


class StateCreateUpdate(base.TreeCreateUpdateView):
    cancellation_url_name = 'state_list'
    create_success_message = "You have successfully inserted State {obj.name}."
    edit_success_message = "State updated successfully"
    model = models.TreeState
    form_class = forms.StateCreateUpdateForm
    success_url_name = 'state_list'


class StateDelete(base.TreeDeleteView):
    cancellation_url_name = 'state_list'
    model = models.TreeState
    success_message = "State successfully deleted"
    success_url_name = 'state_list'


class SurveyList(base.TreeListView):
    create_url_name = 'add_tree'
    model = models.Tree
    order_by = ['trigger']
    select_related = ['root_state__question']
    template_name = 'tree/surveys/list.html'

    def get_queryset(self):
        return super(SurveyList, self).get_queryset().annotate(count=Count('sessions'))


class SurveyExport(base.TreeDetailView):
    model = models.Tree

    def get(self, request, *args, **kwargs):
        tree = self.get_object()
        if tree.has_loops():
            return redirect('list-surveys')
        all_states = tree.get_all_states()
        output = StringIO()
        w = csv.writer(output)
        headings = ["Person", "Date"]
        headings.extend([state.question for state in all_states])
        w.writerow(headings)
        sessions = models.Session.objects.filter(tree=tree)
        for session in sessions:
            values = [str(session.connection), session.start_date]
            transitions = map((lambda x: x.transition), session.entries.all())
            states_w_transitions = {}
            for transition in transitions:
                states_w_transitions[transition.current_state] = transition
            for state in all_states:
                if state in states_w_transitions:
                    values.append(states_w_transitions[state].answer)
                else:
                    values.append("")
            w.writerow(values)
        # rewind the virtual file
        output.seek(0)
        response = HttpResponse(output.read(), content_type='application/ms-excel')
        response["content-disposition"] = "attachment; filename=%s.csv" % tree.trigger
        return response


class SurveyReport(base.TreeDetailView):
    model = models.Tree
    template_name = "tree/surveys/report.html"

    def get_context_data(self, **kwargs):
        tree = self.object
        tag = None
        form = forms.AnswerSearchForm(self.request.GET, tree=tree)
        entry_tags = models.Entry.tags.through.objects
        entry_tags = entry_tags.filter(entry__session__tree=tree)
        entry_tags = entry_tags.select_related('tag')
        tag_map = {}
        for entry_tag in entry_tags:
            if entry_tag.entry_id not in tag_map:
                tag_map[entry_tag.entry_id] = []
            tag_map[entry_tag.entry_id].append(entry_tag.tag)
        # pre-fetch all entries for this tree and create a map so we can
        # efficiently pair everything up in Python, rather than lots of SQL
        entries = models.Entry.objects.filter(session__tree=tree).select_related()
        if tag:
            entries = entries.filter(tags=tag)
        entry_map = {}
        for entry in entries:
            entry.cached_tags = tag_map.get(entry.pk, [])
            state = entry.transition.current_state
            if entry.session.pk not in entry_map:
                entry_map[entry.session.pk] = {}
            entry_map[entry.session.pk][state.pk] = entry
        states = tree.get_all_states()
        sessions = tree.sessions.select_related('connection__contact',
                                                'connection__backend')
        sessions = sessions.order_by('-start_date')
        columns = OrderedDict()
        for state in states:
            columns[state.pk] = []
        # for each session, created an ordered list of (state, entry) pairs
        # using the map from above. this will ease template display.
        for session in sessions:
            session.ordered_states = []
            for state in states:
                try:
                    entry = entry_map[session.pk][state.pk]
                except KeyError:
                    entry = None
                session.ordered_states.append((state, entry))
                if entry:
                    columns[state.pk].append(entry.text)
        # count answers grouped by state
        stats = models.Transition.objects.filter(entries__session__tree=tree,
                                                 entries__in=[e.pk for e in entries])
        stats = stats.values('current_state', 'answer__name')
        stats = stats.annotate(count=Count('answer'))
        stat_map = {}
        for stat in stats:
            current_state = stat['current_state']
            answer = stat['answer__name']
            count = stat['count']
            if current_state not in stat_map:
                stat_map[current_state] = {'answers': {}, 'total': 0}
            stat_map[current_state]['answers'][answer] = count
            stat_map[current_state]['total'] += count
            stat_map[current_state]['values'] = columns[current_state]
        for state in states:
            state.stats = stat_map.get(state.pk, {})
        kwargs.update({
            'form': form,
            'tree': tree,
            'sessions': sessions,
            'states': states,
        })
        return super(SurveyReport, self).get_context_data(**kwargs)


class SurveySessionList(base.TreeDetailView):
    model = models.Tree
    template_name = "tree/surveys/sessions.html"

    def get_context_data(self, **kwargs):
        sessions = self.object.sessions.select_related().order_by('-start_date')[:25]
        kwargs['recent_sessions'] = sessions
        return super(SurveySessionList, self).get_context_data(**kwargs)


class SurveySessionClose(base.TreeDeleteView):
    http_method_names = ['post']
    model = models.Session
    success_message = "Session successfully closed."
    success_url_name = 'recent_sessions'

    def post(self, request, *args, **kwargs):
        """Mark the session as canceled."""
        self.object = self.get_object()
        self.object.cancel()
        return redirect(self.get_success_url())

    def get_success_url(self):
        kwargs = {'pk': self.object.tree.pk}
        return super(SurveySessionClose, self).get_success_url(**kwargs)


class SurveyCreateUpdate(base.TreeCreateUpdateView):
    create_success_message = "You have successfully inserted a Survey {obj.trigger}"
    edit_success_message = "Survey successfully updated"
    form_class = forms.SurveyCreateUpdateForm
    model = models.Tree
    success_url_name = 'list-surveys'
    template_name = "tree/surveys/create_update.html"

    def get_cancellation_url(self):
        if self.mode == self.CREATE_MODE:
            self.cancellation_url_name = 'list-surveys'
            kwargs = {}
        if self.mode == self.UPDATE_MODE:
            self.cancellation_url_name = 'survey-report'
            kwargs = {'pk': self.object.pk}
        return super(SurveyCreateUpdate, self).get_cancellation_url(**kwargs)


class SurveyDelete(base.TreeDeleteView):
    cancellation_url_name = 'survey-report'
    model = models.Tree
    success_message = "Survey successfully deleted"
    success_url_name = 'list-surveys'

    def get_cancellation_url(self):
        return super(SurveyDelete, self).get_cancellation_url(pk=self.object.pk)


class TagList(base.TreeListView):
    create_url_name = 'create-tag'
    model = models.Tag
    order_by = ['name']
    template_name = "tree/tags/list.html"


class TagCreateUpdate(base.TreeCreateUpdateView):
    cancellation_url_name = 'list-tags'
    create_success_message = "Tag successfully saved"
    edit_success_message = "Tag successfully saved"
    model = models.Tag
    form_class = forms.TagCreateUpdateForm
    success_url_name = 'list-tags'


class TagDelete(base.TreeDeleteView):
    cancellation_url_name = 'list-tags'
    model = models.Tag
    success_message = "Tag successfully deleted"
    success_url_name = 'list-tags'
