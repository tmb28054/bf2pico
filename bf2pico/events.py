""" I write the brewlog to brewfather
"""

import json
import logging
import os
import sys
import time


import boto3
import diskcache
import requests


from bf2pico import brewplot


LOG = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(message)s",
    stream=sys.stdout
)
CACHE = diskcache.Cache('~/.bf2pico')

CACHE_TIME = 60 * 60 * 24 * 365 * 10 # 10 years

WEBSITE = os.getenv('WEBSITE', 'https://pico.botthouse.net/')


def settle_active() -> None:
    """ I loop through the active sessions and if there isn't seconds remaining
        move them to finished sessions.
    """
    LOG.debug('running settle_active')
    active_sessions = CACHE.get('active_sessions', [])
    finished_sessions = CACHE.get('finished_sessions', [])
    for session in active_sessions:
        data = CACHE.get(session, {})
        num_of_event = len(data['SessionLogs'])
        if num_of_event:
            last_record = data['SessionLogs'][num_of_event - 1]
            sec_left = last_record.get('SecondsRemaining', None)
            if not sec_left:
                LOG.info('moving %s from active to finished', session)
                active_sessions.remove(session)
                finished_sessions.append(session)

    CACHE.set('active_sessions', active_sessions, expire=CACHE_TIME)
    CACHE.set('finished_sessions', finished_sessions, expire=CACHE_TIME)


def run_session(session: str) -> None:
    """ I run the session
    """
    data = CACHE.get(session, {})
    if not 'SessionLogs' in data:
        data['SessionLogs'] = []
    brewplot.create_graph(data, f'data/{session}.png')

    s3_client = boto3.client('s3')
    year_month_day = time.strftime('%Y-%m-%d', time.localtime(int(time.time())))
    graph_key = f'data/{year_month_day}/{session}.png'
    response = s3_client.upload_file(
        f'data/{session}.png',
        os.getenv('BUCKET', 'picobrew'),
        graph_key
    )
    LOG.debug(json.dumps(response, default=str))
    data_key = f'data/{year_month_day}/{session}.json'
    response = s3_client.put_object(
        Body=json.dumps(CACHE.get(session, {}), indent=2),
        Bucket=os.getenv('BUCKET', 'picobrew'),
        Key=data_key
    )
    LOG.debug(json.dumps(response, default=str))

    data['data_url'] = f'{WEBSITE}{data_key}'
    data['graph_url'] = f'{WEBSITE}{graph_key}'
    data['session'] = session

    update_brewlog(data)


def update_brewlog(data: dict) -> None:
    """_summary_

    Args:
        data (dict): _description_
    """
    user_id = data['session'].split('-')[0]

    response = requests.post(
        f'https://api.brewfather.app/stream?id={user_id}',
        headers={
            'Content-Type': 'json',
        },
        json={
            'name': data.get('device_id', '30aea4c73164'),
            'beer': data.get('Name', 'unknown'),
            'comment': (
                "Brew Complete Graph is {data['graph_url']} "
                "the data file is {data['data_url']}"
            )
        }
    )
    print(response.status_code)
    print(response.text)



def main() -> None:
    """ Main Body
    """
    LOG.debug('Starting True Loop')
    while True:
        # try:
        settle_active()
        LOG.debug('Starting Session Loop')
        for session in CACHE.get('finished_sessions', []):
            run_session(session)

        # except BaseException as error:  # pylint: disable=broad-except
        #     LOG.info('An exception occurred: %s', str(error))

        time.sleep(15 * 60)  # 15 minutes
