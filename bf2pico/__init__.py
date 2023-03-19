""" I provide
        - an sdk for brewfather
        - a translator from brewfather to pico
        - a webapp that can run the pico using brewfather as the gui
"""


import json
import logging
import os
import sys


import boto3
import diskcache


LOG = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(message)s",
    stream=sys.stdout
)

CACHE = diskcache.Cache(
    os.getenv(
        'BF2PICO_CACHE_LOCATION',
        '~/.bf2pico'
    )
)


SSM = boto3.client('ssm')


PARAMETER_PREFIX = '/brewfather'


def get_parameter(name: str) -> str:
    """ I fetch a parameter value

    Args:
        name (str): the parameter name to fetch

    Returns:
        str: the value of the parameter
    """
    LOG.debug('Getting Pramater: %s <-----------------------------------', name)
    if CACHE.get(f'parameters-{name}', None):
        return json.loads(CACHE.get(f'parameter-{name}'))
    response = SSM.get_parameter(
        Name=name,
        WithDecryption=True
    )
    return response['Parameter']['Value']


BUCKET = os.getenv('BUCKET', get_parameter(f'{PARAMETER_PREFIX}/bucket'))


CACHE_TIME = int(os.getenv('BF2PICO_CACHE', '60')) # 1 min

# how long to cache non-presistent data; not a temp cache such as api protection
EPHEMERAL_CACHE_TIME = 60 * 60 * 48 # 2 days

FROM_EMAIL = 'topaz@topazhome.net'

MAIL_SERVER = 'mailrelay.botthouse.net:30001'

MAX_SESSION_TIME = 60 * 60 * 24  # 1 day

# How long to cache presistent data
PERSISTENT_CACHE_TIME = 60 * 60 * 24 * 365 * 10 # 10 years

# Length of time requests should wait for a response form brewfather
REQUESTS_TIMEOUT = 2  # 2 seconds

WEBSITE = os.getenv('WEBSITE',  get_parameter(f'{PARAMETER_PREFIX}/website'))

if not os.getenv('AWS_RETRY_MODE', ''):
    os.environ['AWS_RETRY_MODE'] = 'adaptive'
