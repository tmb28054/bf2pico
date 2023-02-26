""" I provide a standard set of settings
"""


import os


CACHE_TIME = int(os.getenv('BF2PICO_CACHE', '60')) # 1 min

# how long to cache non-presistent data; not a temp cache such as api protection
EPHEMERAL_CACHE_TIME = 60 * 60 * 48 # 2 days

# How long to cache presistent data
PERSISTENT_CACHE_TIME = 60 * 60 * 24 * 365 * 10 # 10 years

# Length of time requests should wait for a response form brewfather
REQUESTS_TIMEOUT = 2  # 2 seconds


WEBSITE = os.getenv('WEBSITE', 'https://pico.botthouse.net/')
