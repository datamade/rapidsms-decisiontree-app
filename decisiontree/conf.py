from django.conf import settings

INVALID_ANSWER_RESPONSE = getattr(settings, 'INVALID_ANSWER_RESPONSE', 'Not a valid answer. Choose one of the following.')

NOTIFICATIONS_ENABLED = getattr(settings, 'DECISIONTREE_NOTIFICATIONS', False)

SESSION_END_TRIGGER = getattr(settings, 'DECISIONTREE_SESSION_END_TRIGGER', 'end')

TIMEOUT = getattr(settings, 'DECISIONTREE_TIMEOUT', 300)
