from datetime import timedelta

from django import template

register = template.Library()

@register.filter(name='duration')
def duration(value, arg=None):
    "Convert numeric value to [HHH:]MM:SS format"
    try:
        num_secs = round(float(value))
        return str(timedelta(seconds=num_secs))
    except:
        return ""
