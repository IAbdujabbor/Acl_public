from django import template

register = template.Library()

@register.filter
def range_filter(value, arg):
    """
    Generate a range of numbers from value to arg (exclusive).
    Usage: {% for i in 0|range_filter:24 %}
    """
    return range(value, arg)

@register.filter
def index(value, i):
    """
    Access an item in a list by its index.
    Usage: {{ my_list|index:0 }}
    """
    try:
        return value[i]
    except (IndexError, TypeError):
        return None

@register.simple_tag(takes_context=True)
def calc_hourly_value(context, daily_value, month, hour):
    """
    Calculate the hourly kWh based on the daily value and the hourly percentage
    for the given month.
    Usage:
      {% calc_hourly_value item.daily_value item.month hour as hourly_val %}
      {{ hourly_val }} kWh
    """
    try:
        hourly_percentages = context.get('hourly_percentages', {})
        percentage_list = hourly_percentages.get(month, [])
        percentage = percentage_list[int(hour)]
        result = daily_value * (percentage / 100)
        return round(result, 2)
    except (KeyError, IndexError, ValueError, TypeError):
        return 0
    


@register.filter
def divideby(value, divisor):
    try:
        return float(value) / float(divisor)
    except (ValueError, ZeroDivisionError):
        return None
    
    

@register.filter
def to_float(value):
    try:
        return float(value)
    except ValueError:
        return None