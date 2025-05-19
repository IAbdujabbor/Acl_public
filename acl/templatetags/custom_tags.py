from django import template

register = template.Library()

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