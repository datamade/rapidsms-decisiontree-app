from model_mommy import mommy

from rapidsms.messages.incoming import IncomingMessage

from decisiontree.handlers.results import ResultsHandler

from .cases import DecisionTreeTestCase


class ResultsTest(DecisionTreeTestCase):

    def setUp(self):
        super(ResultsTest, self).setUp()
        self.q = mommy.make(
            'decisiontree.Message', text='Do you like apples or squash more?')
        mommy.make(
            'decisiontree_multitenancy.MessageLink', linked=self.q, tenant=self.tenant)
        self.fruit = mommy.make(
            'decisiontree.Answer', type='A', name='apples', answer='apples')
        mommy.make(
            'decisiontree_multitenancy.AnswerLink', linked=self.fruit, tenant=self.tenant)
        self.state = mommy.make(
            'decisiontree.TreeState', name='food', message=self.q)
        mommy.make(
            'decisiontree_multitenancy.TreeStateLink', linked=self.state, tenant=self.tenant)
        self.survey = mommy.make(
            'decisiontree.Tree', trigger='food', root_state=self.state)
        mommy.make(
            'decisiontree_multitenancy.TreeLink', linked=self.survey, tenant=self.tenant)

    def _send(self, text):
        msg = IncomingMessage([self.connection], text)
        handler = ResultsHandler(self.router, msg)
        handler.handle(msg.text)
        return handler

    def test_survey_does_not_exist(self):
        handler = self._send('i-do-not-exist')
        response = handler.msg.responses[0]['text']
        self.assertEqual(response, 'Survey "i-do-not-exist" does not exist')

    def test_empty_summary(self):
        handler = self._send('food')
        response = handler.msg.responses[0]['text']
        self.assertEqual(response, 'No summary for "food" survey')

    def test_summary_response(self):
        self.survey.summary = '10 people like food'
        self.survey.save()
        handler = self._send('food')
        response = handler.msg.responses[0]['text']
        self.assertEqual(response, '10 people like food')

    def test_percent_in_summary(self):
        self.survey.summary = 'we are 100%'
        self.survey.save()
        handler = self._send('food')
        response = handler.msg.responses[0]['text']
        self.assertEqual(response, 'we are 100%')
