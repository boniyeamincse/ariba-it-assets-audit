from django import template

register = template.Library()


@register.filter
def portal_number(value, style):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return value
    if style == 'western':
        return f'{number:,}'
    if style != 'indian':
        return str(number)
    prefix = '-' if number < 0 else ''
    digits = str(abs(number))
    if len(digits) <= 3:
        return prefix + digits
    head, tail = digits[:-3], digits[-3:]
    groups = [head[max(0, end - 2):end] for end in range(len(head), 0, -2)]
    return prefix + ','.join([*reversed(groups), tail])
