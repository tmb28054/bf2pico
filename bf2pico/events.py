""" I write the brewlog to brewfather
"""


import argparse
import json
import os
import time


import boto3


from bf2pico import (
    BUCKET,
    LOG,
    MAX_SESSION_TIME,
    PARAMETER_PREFIX,
    brewfather,
    brewplot,
    pico,
    prosaic,
    session,
)


def settle_active() -> None:  # pylint: disable=too-many-locals
    """ I loop through the active sessions and if there isn't seconds remaining
        move them to finished sessions.
    """
    LOG.debug('running settle_active')

    users = prosaic.get_parameters(f'{PARAMETER_PREFIX}/users/')
    s3_client = boto3.client('s3')
    for user_id in users:
        active_key = f'active-sessions/{user_id}.json'
        finished_key = f'finished-sessions/{user_id}.json'

        active_sessions = json.loads(prosaic.s3_get(active_key, '[]'))
        finished_sessions = json.loads(prosaic.s3_get(finished_key, '[]'))

        LOG.info('Active sessions is %s', json.dumps(active_sessions))
        LOG.info('Finished sessions is %s', json.dumps(finished_sessions))

        for _session in active_sessions:
            finished = False
            LOG.info('Session is (%s)', _session)
            session_key = f"sessions/{_session.replace('-', '/')}.json"
            data = json.loads(prosaic.s3_get(session_key, '{}'))


            if (int(time.time()) - int(data.get('Epoch', 0))) > MAX_SESSION_TIME:
                finished = True
            else:
                num_of_event = len(data.get('SessionLogs', []))
                if num_of_event:
                    last_record = data['SessionLogs'][num_of_event - 1]
                    sec_left = last_record.get('SecondsRemaining', None)
                    if not sec_left:
                        finished = True

            if finished:
                LOG.info('moving %s from active to finished', _session)
                active_sessions.remove(_session)
                finished_sessions.append(_session)

                if data.get('Name', 'RINSE') != 'RINSE':
                    LOG.debug('Changing Batch %s to fermenting', data['Pico_Id'])
                    creds = brewfather.BrewAuth(device_id=data['device_id'])
                    pico.change_batch_state(creds, data['Pico_Id'], 'fermenting')

        prosaic.s3_put(json.dumps(active_sessions), active_key)

        # running active sessions
        for session_id in finished_sessions:
            try:
                pico_id = session_id.split('-')[1]
                session_key = f'sessions/{user_id}/{pico_id}.json'
                _session = json.loads(prosaic.s3_get(session_key, '{}'))

                if not os.path.exists('data'):
                    os.makedirs('data')
                local_graph =  f'data/{session_id}.png'
                brewplot.create_graph(_session, local_graph)
                LOG.info('Graph Created %s', local_graph)
                year_month_day = time.strftime('%Y-%m-%d', time.localtime(int(time.time())))
                graph_key = f'graphs/{user_id}/{year_month_day}/{session_id}.png'
                response = s3_client.upload_file(
                    local_graph,
                    BUCKET,
                    graph_key
                )
                LOG.debug(json.dumps(response, default=str))
                session.close_brewing(user_id, session_id, _session)
            except IndexError:
                pass

            finished_sessions.pop(0)

        prosaic.s3_put(json.dumps(finished_sessions), finished_key)


def _options() -> object:
    """
        I provide the argparse option set.

        Returns
            argparse parser object.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('--loop',
                        dest='loop',
                        required=False,
                        default=False,
                        action='store_true',
                        help='Enables Termination Protection')
    return parser.parse_args()


def main() -> None:
    """ Main Body
    """
    args = _options()
    if args.loop:
        LOG.debug('Starting True Loop')
        while True:
            # try:
            settle_active()
            time.sleep(60)  # 1 minutes
    else:
        settle_active()
