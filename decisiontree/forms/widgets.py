from django.forms import TextInput

from ..models import Tag
from ..utils import edit_string_for_tags


class TagWidget(TextInput):

    def render(self, name, value, attrs=None):
        if value is not None and not isinstance(value, str):
            value = edit_string_for_tags(Tag.objects.filter(id__in=value))
        return super(TagWidget, self).render(name, value, attrs)
