from datetime import datetime, date
from decimal import Decimal


def standardize(val):
    if val is None:
        return None
    if isinstance(val, int):
        return str(val)
    if isinstance(val, str) or isinstance(val, unicode):
        return val.strip().lower()
    if isinstance(val, datetime):
        return val.strftime('%Y-%m-%d %H:%M:%S.%f')
    if isinstance(val, date):
        return val.strftime('%Y-%m-%d')
    if isinstance(val, Decimal) or isinstance(val, float):
        return str(round(val, 2))
    raise Exception('Couldn\'t standardize "%s" (type %s)' % (val, type(val)))


def weekday_fields(val):
    """
    Returns a 2-tuple containing:
    1) The Python weekday value for the date passed (Monday == 0 ... Sunday == 6)
    2) A boolean indicating whether the date is on the weekend (Saturday/Sunday)
    """
    assert isinstance(val, datetime) or isinstance(val, date)  # Actually a datetime is an instance of a date, so the first condition isn't necessary...
    return val.weekday(), val.weekday() in (5, 6)
