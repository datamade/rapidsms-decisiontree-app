import datetime
import logging
import re

from django.utils.translation import ugettext as _

from rapidsms.apps.base import AppBase
from rapidsms.messages import OutgoingMessage, IncomingMessage
from rapidsms.models import Connection

from . import conf
from .models import Entry, Session, TagNotification, Transition
from .signals import session_end_signal
from .utils import get_survey


logger = logging.getLogger(__name__)


class App(AppBase):
    registered_functions = {}
    session_listeners = {}

    def handle(self, msg):
        '''
        The handle function should return True or False.
        True tells RapidSMS that the message has been handled.
        False tell RapidSMS that another app should handle it. 
        https://rapidsms.readthedocs.io/en/develop/tutorial/tutorial02.html#handling-a-message 
        
        msg is an instance of a Rapidsms IncomingMessage object.
        https://github.com/rapidsms/rapidsms/blob/347a4d05566ef68d9f494d329cbdc85ce28e811c/rapidsms/messages/incoming.py#L9  
        '''
        # Try to find a survey/tree with the incoming message, i.e., trigger word.
        # If found, then the user wants to (re)start the survey.
        survey = get_survey(msg.text, msg.connection)
        if survey:
            self.start_tree(survey, msg.connection, msg)
            return True 

        sessions = msg.connection.session_set.open().select_related('state')
        if not survey and sessions.count() == 0:
            logger.info('Tree not found: %s', msg.text)
            # Error message handled by the default RapidSMS app
            # https://github.com/rapidsms/rapidsms/blob/master/docs/ref/settings.rst#default_response
            # TODO: customize it.
            return False

        # the caller is part-way though a question
        # tree, so check their answer and respond
        session = sessions.latest('start_date')
        state = session.state
        logger.debug(state)

        end_trigger = conf.SESSION_END_TRIGGER
        if end_trigger is not None and msg.text == end_trigger:
            response = _("Your session with '%s' has ended")
            msg.respond(response % session.tree.trigger)
            self._end_session(session, True, message=msg)
            return True

        # loop through all transitions starting with
        # this state and try each one depending on the type
        # this will be a greedy algorithm and NOT safe if
        # multiple transitions can match the same answer
        transitions = Transition.objects.filter(current_state=state)
        found_transition = None
        for transition in transitions:
            if self.matches(transition.answer, msg):
                found_transition = transition
                break

        # not a valid answer, so remind the user of the valid options.
        if not found_transition:
            if transitions.count() == 0:
                logger.error('No messages found!')
                msg.respond(_("No messages found"))
                self._end_session(session, message=msg)
            else:
                # update the number of times the user has tried
                # to answer this.  If they have reached the
                # maximum allowed then end their session and
                # send them an error message.
                session.num_tries = session.num_tries + 1
                if state.num_retries is not None:
                    if session.num_tries >= state.num_retries:
                        session.state = None
                        msg.respond("Sorry, invalid answer %d times. "
                                    "Your session will now end. Please try again "
                                    "later." % session.num_tries)
                # send them some hints about how to respond
                elif state.message.error_response:
                    msg.respond(state.message.error_response)
                else:
                    invalid_msg = '"{}" is not a valid answer. Please choose one of the following: '.format(msg.text)
                    response = self._concat_answers(invalid_msg, state)
                    msg.respond(response)

                session.save()
            return True

        last_entry = Entry.objects.filter(session=session).order_by('sequence_id').last()
        if last_entry:
            sequence = last_entry.sequence_id + 1
        else:
            sequence = 1
        entry = Entry.objects.create(session=session, sequence_id=sequence,
                                     transition=found_transition,
                                     text=msg.text)
        logger.debug("entry %s saved", entry)

        # apply auto tags
        entry.tags = entry.transition.tags.all()
        # create tag notifications
        TagNotification.create_from_entry(entry)

        # link message log to entry for tag relationship
        if hasattr(msg, 'logger_msg'):
            msg.logger_msg.entry = entry
            msg.logger_msg.save()

        session.state = found_transition.next_state
        session.num_tries = 0
        session.save()

        '''
        If the next state does not have a transition set, then it is a terminal state.
        End the session. 
        '''
        transition_set = Transition.objects.filter(current_state=session.state)
        if not transition_set:
            msg.respond(session.state.message.text)
            self._end_session(session, message=msg)

        # if there is a next question ready to ask
        # send it along
        self._send_message(session, msg)
        # if we haven't returned long before now, we're
        # long committed to dealing with this message
        return True


    def tick(self, session):
        """
        Invoked periodically for each live session to check how long
        since we sent the last question, and decide to resend it or give
        up the whole thing.
        """
        timeout = conf.TIMEOUT
        idle_time = datetime.datetime.now() - session.last_modified
        if idle_time >= datetime.timedelta(seconds=timeout):
            # feed a dummy message to the handler
            msg = IncomingMessage(connection=session.connection,
                                  text="TimeOut")
            self.router.incoming(msg)
            msg.flush_responses()  # make sure response goes out

    def start_tree(self, tree, connection, msg=None):
        """Initiates a new tree sequence, terminating any active sessions"""
        self.end_sessions(connection)
        session = Session(connection=connection,
                          tree=tree, state=tree.root_state, num_tries=0)
        session.save()
        logger.debug("new session %s saved", session)

        # also notify any session listeners of this
        # so they can do their thing
        if tree.trigger in self.session_listeners:
            for func in self.session_listeners[tree.trigger]:
                func(session, False)
        self._send_message(session, msg)

    def _send_message(self, session, msg=None):
        """Sends the next message in the session, if there is one"""
        state = session.state
        if state and state.message:
            response = self._concat_answers(state.message.text, state)

            logger.info("Sending: %s", response)
            if msg:
                msg.respond(response)
            else:
                # we need to get the real backend from the router
                # to properly send it
                real_backend = self.router.get_backend(session.connection.backend.slug)
                if real_backend:
                    connection = Connection(real_backend, session.connection.identity)
                    outgoing_msg = OutgoingMessage(connection, response)
                    self.router.outgoing(outgoing_msg)
                else:
                    # todo: do we want to fail more loudly than this?
                    logger.error("Can't find backend %s. Messages will not "
                                 "be sent", connection.backend.slug)

    def _end_session(self, session, canceled=False, message=None):
        """Ends a session, by setting its state to none,
           and alerting any session listeners"""
        session.close(canceled)
        if session.tree.trigger in self.session_listeners:
            for func in self.session_listeners[session.tree.trigger]:
                func(session, True)
        session_end_signal.send(sender=self, session=session, canceled=canceled,
                                message=message)

    def end_sessions(self, connection):
        """ Ends all open sessions with this connection.
            does nothing if there are no open sessions """
        for session in connection.session_set.open():
            self._end_session(session, True)

    def register_custom_transition(self, name, function):
        """ Registers a handler for custom logic within a
            state transition """
        logger.info("Registering keyword: %s for function %s", name, function.func_name)
        self.registered_functions[name] = function

    def set_session_listener(self, tree_key, function):
        """Adds a session listener to this.  These functions
           get called at the beginning and end of every session.
           The contract of the function is func(Session, is_ending)
           where is_ending = false at the start and true at the
           end of the session.
        """

        logger.info("Registering session listener %s for tree %s", function.func_name, tree_key)
        # I can't figure out how to deal with duplicates, so only allowing
        # a single registered function at a time.
        #
        #        if self.session_listeners.has_key(tree_key):
        #            # have to check existence.  This is mainly for the unit tests
        #            if function not in self.session_listeners[tree_key]:
        #                self.session_listeners[tree_key].append(function)
        #        else:
        self.session_listeners[tree_key] = [function]

    def matches(self, answer, message):
        answer_value = message.text
        """returns True if the answer is a match for this."""
        if not answer_value:
            return False
        if answer.type == "A":
            return answer_value.lower() == answer.answer.lower()
        elif answer.type == "R":
            return re.match(answer.answer, answer_value, re.IGNORECASE)
        elif answer.type == "C":
            if answer.answer in self.registered_functions:
                return self.registered_functions[answer.answer](message)
            else:
                raise Exception("Can't find a function to match custom key: %s", answer)
        raise Exception("Don't know how to process answer type: %s", answer.type)

    def _concat_answers(self, response, state):
        transition_set = Transition.objects.filter(current_state=state).order_by('answer')
        for t in transition_set:
            response += t.answer.helper_text()

        return response

