""" I provide
        - an sdk for brewfather
        - a translator from brewfather to pico
        - a webapp that can run the pico using brewfather as the gui
"""


import logging
import os
import sys


import diskcache


LOG = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(message)s",
    stream=sys.stdout
)

BUCKET = os.getenv('BUCKET', 'picobrew')

CACHE = diskcache.Cache(
    os.getenv(
        'BF2PICO_CACHE_LOCATION',
        '~/.bf2pico'
    )
)

CACHE_TIME = int(os.getenv('BF2PICO_CACHE', '60')) # 1 min

# how long to cache non-presistent data; not a temp cache such as api protection
EPHEMERAL_CACHE_TIME = 60 * 60 * 48 # 2 days

FROM_EMAIL = 'topaz@topazhome.net'

MAIL_SERVER = 'mailrelay.botthouse.net:30001'

MAX_SESSION_TIME = 60 * 60 * 24  # 1 day

PARAMETER_PREFIX = '/brewfather'

# How long to cache presistent data
PERSISTENT_CACHE_TIME = 60 * 60 * 24 * 365 * 10 # 10 years

# Length of time requests should wait for a response form brewfather
REQUESTS_TIMEOUT = 2  # 2 seconds

WEBSITE = os.getenv('WEBSITE', 'https://pico.botthouse.net/')
