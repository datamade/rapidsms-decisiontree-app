import datetime

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils.encoding import python_2_unicode_compatible

from colorful.fields import RGBColorField


@python_2_unicode_compatible
class Message(models.Model):
    text = models.CharField(
        max_length=500, verbose_name="message text",
        help_text="The text to send to the user, e.g., a question, completion text.")
    error_response = models.CharField(
        max_length=160, blank=True,
        help_text="Optional error message if the user does not send a valid response.")

    def __str__(self):
        return u"Q%s: %s" % (self.pk, self.text)


@python_2_unicode_compatible
class Tree(models.Model):
    """A decision tree.

    Trees have a trigger, which is is the incoming message that will initiate a
    tree.  They also have a root state which is the first state the tree will
    be in.  The Message linked to the root state will be the one that is sent
    when the tree is initiated.  The remaining logic of the tree is
    encapsulated by the Transition objects, which define how answers to
    messages move from one state to the next.

    A tree also has optional completion text, which is the message that will be
    sent to the user when they reach a node in the tree with no possible
    transitions.
    """
    trigger = models.CharField(
        max_length=30, unique=True, verbose_name="Keyword",
        help_text="The incoming message which triggers this Tree.")
    root_state = models.ForeignKey(
        "TreeState", related_name="tree_set",
        help_text="The first Message sent when this Tree is triggered, "
                  "which may lead to many more.")
    summary = models.CharField(max_length=160, blank=True)

    class Meta(object):
        # The permission required for this tab to display in the UI.
        permissions = [
            ("can_view", "Can view tree data"),
        ]
        verbose_name = 'survey'

    def __str__(self):
        return u"T%s: %s -> %s" % (self.pk, self.trigger, self.root_state)

    def get_all_states(self):
        all_states = []
        all_states.append(self.root_state)
        if self.root_state:
            self.root_state.add_all_unique_children(all_states)
        return all_states

    def has_loops(self):
        return self.root_state.has_loops_below()


@python_2_unicode_compatible
class Answer(models.Model):
    """A response to a message.

    There are three possible types of answers:

    The simplest is an exact answer. Messages will only match this answer if
    the text is exactly the same as the answer specified.

    The second is a regular expression.  In this case the system will run a
    regular expression over the message and match the answer if the regular
    expression matches.

    The final type is custom logic.  In this case the answer should be a
    special keyword that the application developer defines. The application
    developer can then register a function tied to this keyword with the tree
    app and the tree app will call that function to see if the answer should
    match. The function should return any value that maps to True if the answer
    is valid, otherwise any value that maps to False.
    """
    ANSWER_TYPES = (
        ('A', 'Exact Match'),
        ('R', 'Regular Expression'),
        ('C', 'Custom Logic'),
    )
    name = models.CharField(max_length=30, unique=True)
    type = models.CharField(max_length=1, choices=ANSWER_TYPES)
    answer = models.CharField(max_length=160)
    color = RGBColorField(default=u"#000000")
    description = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return self.name

    def helper_text(self):
        if self.type == "A":
            if self.description:
                return "\n(%s) %s" % (self.answer, self.description)
            return self.answer
        if self.type == "R":
            if self.description:
                return self.description
            # this will be ugly
            return self.answer
        if self.type == "C":
            if self.description:
                return self.description
            # this might be ugly
            return self.answer


@python_2_unicode_compatible
class TreeState(models.Model):
    """
    A TreeState is a location in a tree.  It is associated with a message and
    a set of answers (transitions) that allow traversal to other states.
    """
    name = models.CharField(max_length=100)
    message = models.ForeignKey(Message)
    num_retries = models.PositiveIntegerField(
        blank=True, null=True,
        help_text="The number of tries the user has to get out of this state. "
                  "If empty, there is no limit. When the number of retries is "
                  "hit, the user's session will be terminated.")

    class Meta:
        verbose_name = 'survey state'

    def __str__(self):
        return self.message.text

    def add_all_unique_children(self, added):
        """
        Adds all unique children of the state to the passed in list.  This
        happens recursively.
        """
        transitions = self.transition_set.select_related('next_state__message')
        for transition in transitions:
            if transition.next_state:
                if transition.next_state not in added:
                    added.append(transition.next_state)
                    transition.next_state.add_all_unique_children(added)

    def has_loops_below(self):
        return TreeState.path_has_loops([self])

    @classmethod
    def path_has_loops(klass, path):
        # we're going to get all unique paths through the this
        # (or until we hit a loop)
        # a path is defined as an ordered set of states
        # if at any point in a path we reach a state we've
        # already seen then we have a loop
        # this is basically a depth first search
        last_node = path[len(path) - 1]
        transitions = last_node.transition_set.all()
        for transition in transitions:
            if transition.next_state:
                # Base case.  We have already seen this state in the path
                if path.__contains__(transition.next_state):
                    return True
                next_path = path[:]
                next_path.append(transition.next_state)
                # recursive case - there is a loop somewhere below this path
                if TreeState.path_has_loops(next_path):
                    return True
        # we trickle down to here - went all the way through without finding any loops
        return False


@python_2_unicode_compatible
class Transition(models.Model):
    """
    A Transition is a way to navigate from one TreeState to another, via an
    appropriate Answer.
    """
    current_state = models.ForeignKey(TreeState)
    answer = models.ForeignKey(Answer, related_name='transitions')
    next_state = models.ForeignKey(TreeState, related_name='next_state')
    tags = models.ManyToManyField('Tag', related_name='transitions', blank=True)

    class Meta(object):
        unique_together = [
            ('current_state', 'answer'),
        ]
        verbose_name = 'path'

    def __str__(self):
        return u"%s : %s --> %s" % (self.current_state, self.answer, self.next_state)


class SessionQuerySet(models.query.QuerySet):
    _closed_conditions = Q(state=None) | Q(canceled=True)

    def open(self):
        return self.exclude(self._closed_conditions)

    def closed(self):
        return self.filter(self._closed_conditions)


@python_2_unicode_compatible
class Session(models.Model):
    """
    A Session represents a single person's current status traversing through a
    Tree. It is a way to persist information about what state they are in, how
    many retries they have had, etc. so that we aren't storing all of that
    in-memory.
    """
    connection = models.ForeignKey('rapidsms.Connection')
    tree = models.ForeignKey(Tree, related_name='sessions')
    start_date = models.DateTimeField(auto_now_add=True)
    state = models.ForeignKey(
        TreeState, blank=True, null=True,
        help_text="None if the session is complete.")
    num_tries = models.PositiveIntegerField(
        help_text="The number of times the user has tried to respond to the current message.")
    # this flag stores the difference between completed
    # on its own, or manually canceled.
    canceled = models.NullBooleanField(blank=True, null=True)
    last_modified = models.DateTimeField(auto_now=True, null=True)

    objects = SessionQuerySet.as_manager()

    def __str__(self):
        state = self.state or "completed"
        return u"%s : %s" % (self.connection.identity, state)

    def cancel(self):
        return self.close(canceled=True)

    def close(self, canceled=False):
        """Forcibly close this session.

        No operation if session is already closed.
        """
        # TODO: call app listeners?
        if not self.is_closed():
            self.state = None
            self.canceled = canceled
            self.save()

    def is_closed(self):
        return not bool(self.state_id) or self.canceled

    def is_open(self):
        return bool(self.state_id) and not self.canceled


@python_2_unicode_compatible
class Entry(models.Model):
    """
    An Entry is a single successful movement within a Session.  It represents
    an accepted Transition from one state to another within the tree.
    """
    session = models.ForeignKey(Session, related_name='entries')
    sequence_id = models.IntegerField()
    transition = models.ForeignKey(Transition, related_name='entries')
    time = models.DateTimeField(auto_now_add=True, db_index=True)
    text = models.CharField(max_length=160)
    tags = models.ManyToManyField('Tag', related_name='entries')

    class Meta(object):
        verbose_name_plural = "Entries"
        ordering = ('sequence_id',)

    def __str__(self):
        return u"%s-%s: %s - %s" % (
            self.session.pk, self.sequence_id,
            self.transition.current_state.message, self.text)

    def display_text(self):
        # assume that the display text is just the text,
        # since this is what it is for free text entries
        return self.text

    def meta_data(self):
        return "%s - %s %s" % (
            self.session.person.phone,
            self.time.strftime("%a %b %e"),
            self.time.strftime("%I:%M %p"))


@python_2_unicode_compatible
class Tag(models.Model):
    name = models.CharField(unique=True, max_length=100)
    recipients = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='tags')

    def __str__(self):
        return self.name


@python_2_unicode_compatible
class TagNotification(models.Model):
    tag = models.ForeignKey(Tag)
    user = models.ForeignKey(settings.AUTH_USER_MODEL)
    entry = models.ForeignKey(Entry)
    sent = models.BooleanField(default=False)
    date_added = models.DateTimeField()
    date_sent = models.DateTimeField(null=True, blank=True)

    class Meta(object):
        unique_together = ('tag', 'user', 'entry')

    def __str__(self):
        return self.user

    @classmethod
    def create_from_entry(cls, entry):
        for tag in entry.tags.all():
            for user in tag.recipients.all():
                TagNotification.objects.get_or_create(tag=tag, entry=entry, user=user)

    def save(self, **kwargs):
        if not self.pk:
            self.date_added = datetime.datetime.now()
        super(TagNotification, self).save(**kwargs)
