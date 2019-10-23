import datetime
from six.moves.urllib.parse import urljoin
from six import string_types
import requests
import dateutil.parser

import re

API_URL = 'http://finder.creodias.eu/resto/api/collections/'
MAX_PAGES = 1000
MAX_RECORDS = 1000


class RequestError(Exception):
    def __init__(self, message, errors):
        super().__init__(message)
        self.errors = errors


def query(collection=None, start_date=None, end_date=None, geometry=None, **kwargs):
    """ Query the EOData Finder API

    Parameters
    ----------
    collection: str, optional
        the data collection, corresponding to various satellites
    start_date: str or datetime
        the start date of the observations, either in iso formatted string or datetime object
    end_date: str or datetime
        the end date of the observations, either in iso formatted string or datetime object
        if no time is specified, time 23:59:59 is added.
    geometry: str
        area of interest as well-known text string
    **kwargs
        Additional arguments can be used to specify other query parameters,
        e.g. productType=L1GT
        See https://creodias.eu/eo-data-finder-api-manual for a full list

    Returns
    -------
    dict[string, dict]
        Products returned by the query as a dictionary with the product ID as the key and
        the product's attributes (a dictionary) as the value.
    """
    url = API_URL
    if collection:
        url = urljoin(API_URL, collection)
    url += f'/search.json?'
    if start_date:
        start_date = _parse_date(start_date)
        url += f'&startDate={start_date.isoformat()}'
    if end_date:
        end_date = _parse_date(end_date)
        end_date = _add_time(end_date)
        url += f'&completionDate={end_date.isoformat()}'
    if geometry:
        geometry = _convert_wkt(geometry)
        url += f'&geometry={geometry}'
    for attr, value in sorted(kwargs.items()):
        value = _parse_argvalue(value)
        url += f'&{attr}={value}'

    url += f'&maxRecords={MAX_RECORDS}'
    print(url)

    query_response = {}
    for page in range(1000):
        url_page = url + f'&page={page + 1}'
        response = requests.get(url_page)
        response.raise_for_status()
        data = response.json()
        if data['properties']['itemsPerPage'] == 0:
            break
        if page == 999:
            raise RequestError(f'The query is too large.')
        for feature in data['features']:
            query_response[feature['id']] = feature
    return query_response


def _parse_date(date):
    pattern = re.compile(f'''^[0-9]{4}-[0-9]{2}-[0-9]{2}(T[0-9]{2}:[0-9]{2}:[0-9]{2}'''
                         f'''(\\.[0-9]+)?(|Z|[\\+\\-][0-9]{2}:[0-9]{2}))?$'''
                         )
    if isinstance(date, datetime.datetime):
        return date
    elif pattern.match(date):
        return dateutil.parser.parse(date)
    else:
        raise ValueError('Date {date} is not in a valid format. Use Datetime object or iso string')


def _add_time(date):
    if date.hour == 0 and date.minute == 0 and date.second == 0:
        date = date + datetime.timedelta(hours=23, minutes=59, seconds=59)
        return date
    return date


def _convert_wkt(geometry):
    try:
        return geometry.replace(", ", ",").replace(" ", "", 1).replace(" ", "+")
    except Exception:
        raise ValueError('Geometry must be in well-known text format')


def _parse_argvalue(value):

    if isinstance(value, string_types):
        value = value.strip()
        if not any(
            value.startswith(s[0]) and value.endswith(s[1])
            for s in ["[]", "{}", "//", "()"]
        ):
            value = re.sub(r"\s", r"\ ", value, re.M)
        return value

    elif isinstance(value, (list, tuple)):
        # Handle value ranges
        if len(value) == 2:
            value = "[{},{}]".format(*value)
            return value
        else:
            raise ValueError(
                "Invalid number of elements in list. Expected 2, received "
                "{}".format(len(value))
            )

    else:
        raise ValueError(
            "Additional arguments can be either string or tuple/list of 2 values"
        )
