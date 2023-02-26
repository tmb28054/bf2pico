""" I write the brewlog to brewfather
"""


import argparse
import json
import sys
import time


import boto3


from bf2pico import (
    BUCKET,
    LOG,
    PARAMETER_PREFIX,
    WEBSITE,
    brewfather,
    brewplot,
    pico,
    prosaic,
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

        active_sessions = json.loads(prosaic.s3_get(active_key, '[]]'))
        finished_sessions = json.loads(prosaic.s3_get(finished_key, '[]'))

        LOG.info('Finished sessions is %s', json.dumps(finished_sessions))

        for session in active_sessions:
            session_key = f"sessions/{session.replace('-', '/')}.json"
            data = json.loads(prosaic.s3_get(session_key, '{}'))

            num_of_event = len(data['SessionLogs'])
            if num_of_event:
                last_record = data['SessionLogs'][num_of_event - 1]
                sec_left = last_record.get('SecondsRemaining', None)
                if not sec_left:
                    LOG.info('moving %s from active to finished', session)
                    active_sessions.remove(session)
                    finished_sessions.append(session)

                    if data['Name'] != 'RINSE':
                        LOG.debug('Changing Batch %s to fermenting', data['Pico_Id'])
                        creds = brewfather.BrewAuth(device_id=data['device_id'])
                        pico.change_batch_state(creds, data['Pico_Id'], 'fermenting')


        prosaic.s3_put(json.dumps(active_sessions), active_key)

        # running active sessions
        for session_id in finished_sessions:
            pico_id = session_id.split('-')[1]
            session_key = f'sessions/{user_id}/{pico_id}.json'
            session = json.loads(prosaic.s3_get(session_key, '{}'))

            local_graph =  f'data/{session_id}.png'
            brewplot.create_graph(session, local_graph)
            LOG.info('Graph Created %s', local_graph)
            year_month_day = time.strftime('%Y-%m-%d', time.localtime(int(time.time())))
            graph_key = f'graphs/{user_id}/{year_month_day}/{session_id}.png'
            response = s3_client.upload_file(
                local_graph,
                BUCKET,
                graph_key
            )
            LOG.debug(json.dumps(response, default=str))
            # session['session'] = session
            LOG.info(
                f"""
                    name = '{session['Name']}'
                    user_id = '{user_id}'
                    device_id = '{session['device_id']}'
                    comment = 'boobs'
                """
            )
            brewfather.update_brewlog(
                session['Name'],
                user_id,
                session['device_id'],
                f'Brew Complete Graph is {WEBSITE}{graph_key} '\
                    f'the data file is {WEBSITE}/{session_key}'
            )
            # finished_sessions.pop(session_id)

            sys.exit(1)

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
            time.sleep(15 * 60)  # 15 minutes
    else:
        settle_active()
