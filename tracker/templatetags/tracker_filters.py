"""
Custom Template Filters — tracker app
=======================================
Usage in templates: {% load tracker_filters %}
                    {{ amount|inr }}  →  ₹1,23,456
"""

from django import template
from decimal import Decimal, InvalidOperation

register = template.Library()


@register.filter(name='inr')
def inr_format(value):
    """
    Format a number in Indian Rupee notation with ₹ symbol.

    Indian numbering: last 3 digits grouped, then groups of 2.
    Example: 1234567 → ₹12,34,567
             100000  → ₹1,00,000
             50      → ₹50

    Algorithm:
    1. Convert to integer (no paise per assignment)
    2. Take last 3 digits → rightmost group
    3. Remaining digits grouped by 2 from right
    4. Join with commas, prepend ₹
    """
    try:
        amount = int(Decimal(str(value)))
    except (InvalidOperation, TypeError, ValueError):
        return value  # Return as-is if not a valid number

    if amount < 0:
        return f"-{inr_format(-amount)}"

    s = str(amount)

    if len(s) <= 3:
        return f"₹{s}"

    # Last 3 digits
    last3 = s[-3:]
    rest  = s[:-3]

    # Group remaining in chunks of 2, from right
    groups = []
    while len(rest) > 2:
        groups.insert(0, rest[-2:])
        rest = rest[:-2]
    if rest:
        groups.insert(0, rest)

    return f"₹{','.join(groups)},{last3}"


@register.filter(name='inr_plain')
def inr_plain(value):
    """Same as inr but without the ₹ symbol — useful for CSV export context."""
    formatted = inr_format(value)
    return formatted.lstrip('₹') if isinstance(formatted, str) else formatted


@register.filter(name='subtract')
def subtract(value, arg):
    """Template filter: {{ a|subtract:b }} → a - b"""
    try:
        return Decimal(str(value)) - Decimal(str(arg))
    except (InvalidOperation, TypeError):
        return 0


@register.filter(name='percentage')
def percentage(value, total):
    """Template filter: {{ repaid|percentage:principal }} → 42.3%"""
    try:
        v = Decimal(str(value))
        t = Decimal(str(total))
        if t == 0:
            return "0%"
        return f"{(v / t * 100):.1f}%"
    except (InvalidOperation, TypeError, ZeroDivisionError):
        return "0%"
