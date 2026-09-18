from django import template
from django.utils.safestring import mark_safe

from apps.chat.markdown import render_assistant_markdown

register = template.Library()


@register.filter(is_safe=True)
def render_markdown(value):
    return mark_safe(render_assistant_markdown(value))
