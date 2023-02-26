""" i provide the session log functions
"""


from datetime import datetime
import json
import random
import string
import time


from bf2pico import (
    CACHE,
    LOG,
    brewfather,
    pico,
    prosaic,
)


DEFAULT_SESSION_DATA = {
    'ZSeriesID': 460,
    'ProfileID': 14392,
    'LastLogID': None,
    'RecipeID': None,
    'StillUID': None,
    'StillVer': None,
    'GroupSession': False,
    'RecipeGuid': None,
    'ClosingDate': None,
    'Deleted': False,
    'Notes': None,
    'Lat': 32.811131,
    'Lng': -117.251457,
    'CityLat': 32.715736,
    'CityLng': -117.161087,
    'Active': True,
    'Pressure': 0,
    'MaxTempAddedSec': 0,
    'ProgramParams': {
        'Duration': 0.0,
        'Water': 0.0,
        'Intensity': 0.0,
        'Temperature': 0.0,
        'Abv': None,
        'Ibu': None
    },
    'SessionLogs': [],
    'SecondsRemaining': None
}


def _gid() -> str:
    """ I generate a 32 char random alphanumeric string
    """
    return \
        str(
            ''.join(
                random.choices(
                    string.ascii_letters + string.digits,
                    k=32
                )
            )
        ).upper()



def new_session_data(creds: object, session_data: dict) -> dict:
    """ I create a new session data and update the batch to brewing

    Args:
        creds (object): brewfather auth object
        session_data (dict): key word arguments

    Returns:
        dict: of the session data
    """
    pico_id = CACHE.get(f'{creds.device_id}-recipe', 0)
    LOG.debug('pico_id = %s', pico_id)
    data = {
        'GUID': _gid(),
        'CreationDate': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3],
        'Pico_Id': pico_id,
    }
    # populate from request
    for key, value in session_data.items():
        if key not in data and key != 'data':
            data[key] = value
    for key, value in session_data.get('data', {}).items():
        if key not in data and key != 'data':
            data[key] = value

    # populate from defaults
    for key, value in DEFAULT_SESSION_DATA.items():
        if key not in data:
            data[key] = value

    LOG.debug('session_data is')
    LOG.debug(json.dumps(data, indent=2))

    # Move from planning to brewing
    if data.get('Name', '') != 'RINSE':
        pico.change_batch_state(creds, pico_id, 'brewing')

    return data


def next_session_id(user_id: str) -> int:
    """ I determine the next session id for the brewfather user

    Args:
        user_id (str): the brewfather user_id

    Returns:
        int: next session id to use
    """
    current = prosaic.s3_getobjects(f'sessions/{user_id}/')
    return  104185 + len(current)


def next_log_event_id(sessions: list) -> int:
    """ I return the next log event id for the session.

    Args:
        sessions (list): list of sessions where a session is a dict

    Returns:
        int: the id to use for brew event log
    """
    return 21204557 + len(sessions)


class BrewLog:
    """
        I manage the session of a brew event.

        kwargs:
            device_id: the device id to use for the session
    """
    def __init__(self, **kwargs) -> object:
        """ I am the init to a brew log
        """
        device_id = kwargs.get('device_id', None)
        if not device_id:
            LOG.info('BewLog missing device_id')
            raise Exception('BewLog missing device_id')  # pylint: disable=broad-exception-raised

        self.creds = brewfather.BrewAuth(device_id=device_id)
        self.user_id = self.creds.user_id

        self._id = kwargs.get('_id', None)
        if not self._id:
            self._id = next_session_id(self.user_id)


        self.index = f'{self.user_id}-{self._id}'
        self.cache_key = f'sessions/{self.user_id}/{self._id}.json'

        self.data = prosaic.s3_get(self.cache_key, None)
        if not self.data:
            session_data = kwargs.copy()
            session_data['ID'] = str(self._id)
            LOG.debug(json.dumps(session_data, indent=2))
            self.data = new_session_data(self.creds, session_data)

        if isinstance(self.data, str):
            self.data = json.loads(self.data)

    def save(self) -> None:
        """ I save the save the brew log session
        """
        prosaic.s3_put(json.dumps(self.data), self.cache_key)

        active_key = f'active-sessions/{self.creds.user_id}.json'
        finished_key = f'finished-sessions/{self.creds.user_id}.json'

        active_sessions = json.loads(prosaic.s3_get(active_key, '[]'))
        finished_sessions = json.loads(prosaic.s3_get(finished_key, '[]'))

        if self.index not in active_sessions:
            active_sessions.append(self.index)

        num_of_events = len(self.data.get('SessionLogs', []))

        if num_of_events:
            seconds_remaining = self.data['SessionLogs']\
                [num_of_events - 1].get('SecondsRemaining', 0)
            if not seconds_remaining:
                active_sessions.remove(self.index)
                if self.index not in finished_sessions:
                    finished_sessions.append(self.index)
                pico.change_batch_state(self.creds, self._id, 'fermenting')

        prosaic.s3_put(json.dumps(active_sessions), active_key)
        prosaic.s3_put(json.dumps(finished_sessions), finished_key)

    def add_logs(self, log_event) -> None:
        """ I add event logs to the session.
        """
        event_id = next_log_event_id(self.data['SessionLogs'])
        if 'epoch' not in log_event:
            log_event['epoch'] = int(time.time())

        self.data['SessionLogs'].append(log_event)

        result = {
            'ID': event_id,
            'ZSessionID': self._id,
            'LogDate': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3],
            'ThermoBlockTemp': log_event['ThermoBlockTemp'],
            'WortTemp': log_event['WortTemp'],
            'AmbientTemp': log_event['AmbientTemp'],
            'DrainTemp': log_event['DrainTemp'],
            'TargetTemp': float(log_event['TargetTemp']),
            'ValvePosition': float(log_event['ValvePosition']),
            'KegPumpOn': False,
            'DrainPumpOn': False,
            'StepName': log_event['StepName'],
            'ErrorCode': log_event['ErrorCode'],
            'PauseReason': log_event['PauseReason'],
            'rssi': log_event['rssi'],
            'netSend': log_event['netSend'],
            'netWait': log_event['netWait'],
            'netRecv': log_event['netRecv'],
            'SecondsRemaining': None,
            'StillSessionLog': None,
            'StillSessionLogID': None
        }
        return result
