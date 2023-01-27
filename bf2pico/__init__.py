"""
    I am an SDK for brokering, loading recipes from brewfather, and
    transforming them into pico runbooks.

   Environment variables can be provided to bypass the requirement to
   include initialization.

    BF2PICO_CACHE: The cache time in seconds
    BREWFATHER_USERID: The userid for brewfather
    BREWFATHER_APIKEYL: The apikey for brewfather

"""


from datetime import datetime
import base64
import json
import logging
import os
import random
import string
import sys


import requests
import diskcache


LOG = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    stream=sys.stdout
)
CACHE = diskcache.Cache('~/.bf2pico')
CACHE_TIME = int(os.getenv('BF2PICO_CACHE', '60')) # 1 min
DB_CACHE_TIME = 60 * 60 * 24 * 365 * 10 # 10 years


DRAINTIME = 8


RECIPE_NAME_BY_ID = {}
RECIPE_ID_BY_NAME = {}
RECIPE_BY_ID = {}

RECIPE_COUNTER = 170335

PICO_LOCATIONS = {
    'PassThru': 0,
    'Whirlpool': 0,
    'Mash': 1,
    'Adjunct1': 2,
    'Adjunct2': 3,
    'Adjunct3': 4,
    'Adjunct4': 5,
    'Pause': 6,
}


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


def celsius2fahrenheit(celsius: int) -> int:
    """
        I convert celsius to fahrenheit

        Args
            celsius: temp in celsius

        Returns temp in fahrenheit
    """
    return int((celsius * 1.8) + 32)


def _gen_pico(recipe: dict) -> dict:
    """
        I generate a pico run plan from a brewfather recipe.

        Args
            recipe: A recipe from brewfather in dict form.

        Returns: A pico list of steps to brew the recipe.
    """

    steps = []
    whirlpool = 0

    # build the mash steps
    for step in recipe['mash']['steps']:
        steps += [
            { # Raise the water temp
                'Drain':  0,
                # 'hop_time': '',
                'Location': PICO_LOCATIONS.get('PassThru', 0),
                'Name': 'Heat Mash',
                'Time': 0,
                'Temp': celsius2fahrenheit(step['stepTemp']),
                # 'total_time': 0
            },
            { # Convert carbs to sugar
                'Drain':  DRAINTIME,
                # 'hop_time': '',
                'Location': PICO_LOCATIONS.get('Mash', 0),
                'Name': 'Mash',
                'Time': step['stepTime'],
                'Temp': celsius2fahrenheit(step['stepTemp']),
                # 'total_time': step['stepTime'] + DRAINTIME
            },
        ]

    # add a step to heat to a boil
    steps += [
        {
            'Drain':  0,
            # 'hop_time': '',
            'Location': PICO_LOCATIONS.get('PassThru', 0),
            'Name': 'Heat to Boil',
            'Time': 0,
            'Temp': 207,
            # 'total_time': 0
        },
    ]

    boil_time = recipe['boilTime']

    # Build a dict of our hops
    hops = {}
    for hop in recipe['hops']:
        if hop['use'] == 'Aroma':
            whirlpool = hop['time']
        elif hop['use'] == 'Boil':
            hops[hop['time']] = [hop]

    adjusted_hops = []
    sub = 0
    for hop in sorted(hops):
        hop -= - sub
        sub += hop
        adjusted_hops.append(hop)

    # run the hops in order they should be added
    slot = 1
    for index in reversed(adjusted_hops):
        if boil_time < index:
            LOG.info('boil time less then hop time, adjusting boil time')
            boil_time = index

        # how long to boil before next hop step
        step_time = boil_time - index
        if slot == 1 and step_time:
            steps += [
                {
                    'Drain':  0,
                    # 'hop_time': '',
                    'Location': PICO_LOCATIONS.get('PassThru', 0),
                    'Name': 'Pre-hop Boil',
                    'Time': step_time,
                    'Temp': 207,
                    # 'total_time': step_time
                }
            ]

        # add the hops
        steps += [
            {
                'Drain':  0,
                # 'hop_time': index,
                'Location': PICO_LOCATIONS.get(f'Adjunct{slot}', 0),
                'Name': f'Hops {slot}',
                'Time': index,
                'Temp': 207,
                # 'total_time': index
            },
        ]

        boil_time = index
        slot += 1

    if whirlpool:
        steps += [
            {
                'Drain':  0,
                # 'hop_time': '',
                'Location': PICO_LOCATIONS.get('PassThru', 0),
                'Name': 'Cool to Whirlpool',
                'Time': 0,
                'Temp': 175,
                # 'total_time': 0
            },
            {
                'Drain':  5,
                # 'hop_time': whirlpool,
                'Location': PICO_LOCATIONS.get(f'Adjunct{slot}', 0),
                'Name': 'Whirlpool',
                'Time': whirlpool,
                'Temp': 175,
                # 'total_time': whirlpool + 5
            },
        ]

    pico = {
        'ID': recipe['_id'],
        'Name': recipe['name'],
        'StartWater': 16.69,
        'TypeCode': 'Beer',
        'Steps': steps
    }
    return pico


def get_recipes(auth) -> dict:
    """
        I get the all recipes from brewfather.

        Args
            auth: the base64 auth string

        Returns: Dict of recipes with the key being the recipe name
                    and the value being the brewfather recipe.
    """
    if 'recipes' in CACHE:
        return CACHE[f'{auth}recipes']
    recipes = {}
    url = 'https://api.brewfather.app/v1/recipes?limit=50&complete=True'
    response = requests.get(
        url,
        headers={
            'Content-Type': 'json',
            'authorization': f'Basic {auth}'
        }
    )

    loop_count = 0
    while True:
        count = 1
        for recipe in json.loads(response.text):
            recipes[recipe['name']] = recipe
            count += 1
        if count < 50:
            break
        loop_count += 1
        response = requests.get(f'{url}&offset={loop_count * 50}')

    CACHE.set(f'{auth}recipes', recipes, expire=CACHE_TIME)

    return recipes


def get_batchs(auth) -> dict:
    """
        I get a list of batchs which are marked for brewing in brewfather

        Args
            auth: the base64 auth string

        Returns: List of dict representing the a batch marked for brewing
                    in brewfather
    """
    if 'batchs' in CACHE:
        return CACHE[f'{auth}batchs']

    response = requests.get(
        'https://api.brewfather.app/v1/batches?limit=50&status=Brewing',
        headers={
            'Content-Type': 'json',
            'authorization': f'Basic {auth}'
        }
    )
    result = json.loads(response.text)
    CACHE.set(f'{auth}batchs', result, expire=CACHE_TIME)
    return result


def _new_session_id(user_id) -> int:
    """ I return a session id that is unique based on the userid.
    """
    counter = 104185
    while f'{user_id}-{counter}' in CACHE:
        counter += 1
    return counter


def _new_log_event_id(user_id) -> int:
    """ new log event id
    """
    counter = 21204557
    while f'{user_id}-event-{counter}' in CACHE:
        counter += 1
    CACHE.set(f'{user_id}-event-{counter}', True, expire=DB_CACHE_TIME)
    return counter


def new_session_data(_id, kwargs) -> dict:
    """ tbd
    """
    data = {
        'ID': _id,
        'GUID': _gid(),
        'CreationDate': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3]
    }

    # populate from request
    for key, value in kwargs.get('data', {}).items():
        if key not in data:
            data[key] = value

    # populate from defaults
    for key, value in DEFAULT_SESSION_DATA.items():
        if key not in data:
            data[key] = value

    return data


class BrewLog:
    """
        I manage the session of a brew event.
    """
    def __init__(self, **kwargs) -> object:
        """
            tdb
        """
        self.logger = logging.getLogger(__name__)
        self.logger.debug('Creating RecipeDB')

        self.userid = kwargs.get(
            'userid',
            os.getenv('BREWFATHER_USERID', None)
        )

        if kwargs.get('_id', None):
            self._id = kwargs.get('_id')
            self.data = CACHE.get(
                f'{self.userid}-{self._id}',
                new_session_data(self._id, kwargs)
            )
        else:
            self._id = _new_session_id(self.userid)
            self.data = new_session_data(self._id, kwargs)

        self.index = f'{self.userid}-{self._id}'

    def save(self) -> None:
        """ tbd
        """
        CACHE.set(
            self.index,
            self.data,
            expire=DB_CACHE_TIME
        )
        filename = f'data/session-{self.index}.json'
        with open(filename, 'w', encoding='utf8') as handler:
            handler.write(
                json.dumps(self.data, indent=2)
            )

    def add_logs(self, log_event) -> None:
        """ tbd
        """
        event_id = _new_log_event_id(self.userid)
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


class RecipeDB:
    """_summary_

    Raises:
        Exception: _description_
        Exception: _description_

    Returns:
        _type_: _description_
    """
    def __init__(self, **kwargs) -> object:
        """
            tdb
        """
        self.logger = logging.getLogger(__name__)
        self.logger.debug('Creating RecipeDB')

        self.userid = kwargs.get(
            'userid',
            os.getenv('BREWFATHER_USERID', None)
        )
        self.counter = 170335
        self.recipe_list = {}

    def load(self) -> None:
        """ tbd
        """
        self.recipe_list = CACHE[self.userid]

    def save(self) -> None:
        """ tbd
        """
        CACHE.set(
            self.userid,
            self.recipe_list,
            expire=DB_CACHE_TIME
        )

    def add_recipe(self, recipe) -> None:
        """ tbd
        """
        self.recipe_list[self.counter] = recipe
        self.counter += 1

    def fetch_recipe(self, _id: int):
        """_summary_

        Args:
            _id (_type_): _description_
        """
        return self.recipe_list.get(
            int(_id),
            {
                'error': f'recipe for id {_id} not found',
                'recipes': self.recipe_list

            }
        )

    def list_recipes(self) -> None:
        """ tbd
        """
        recipes = []
        for _id, recipe in self.recipe_list.items():
            recipes.append(
                {
                    'ID': _id,
                    'Name': recipe['Name'],
                    'Kind': 0,
                    'Uri': None,
                    'Abv': -1,
                    'Ibu': -1
                }
            )
        return \
            {
                'Kind': 1,
                'Offset': 0,
                'SearchString': None,
                'MaxCount': 0,
                'TotalResults': len(recipes),
                'Recipes':  recipes
            }


class BrewFather:  # pylint: disable=R0903
    """
        I am a class to abstract fetching recipes from brewfather then transform
        them into commands for the pico zymatic.

        Usage
                Recipes = BrewFather(
                    userid=userid,
                    apikey=apikey
                )

                print(Recipes.pico) <- returns a list of recipes in pico format.
    """
    def __init__(self, **kwargs) -> object:
        """
            tdb
        """
        self.logger = logging.getLogger(__name__)
        self.logger.debug('Creating BrewFather Recipe Object')

        self.recipes = None
        self.batchs = None

        self.userid = kwargs.get(
            'userid',
            os.getenv('BREWFATHER_USERID', None)
        )
        if not self.userid:
            raise Exception('Missing userid')

        self.apikey = kwargs.get(
            'apikey',
            os.getenv('BREWFATHER_APIKEY', None)
        )
        if not self.apikey:
            raise Exception('Missing apikey')

        self.auth_str = \
            f"{self.userid}:{self.apikey}"

        self.auth = \
            base64.b64encode(self.auth_str.encode('ascii')).decode("utf-8")

    def pico(self) -> dict:
        """
            I return a list of batchs dedup'ing multiple batchs with of the
            same recipe.

            Returns: list of dict where each dict is a option for the pico.
        """
        result = []
        batch_list = []

        recipes = get_recipes(self.auth)
        LOG.debug(json.dumps(recipes, indent=2))
        for batch in get_batchs(self.auth):
            name = batch['recipe']['name']
            if name not in batch_list:
                result.append(
                    _gen_pico(
                        recipes[name]
                    )
                )
                batch_list.append(name)
        return result

    def start_session(self) -> dict:
        """
            I return a list of batchs dedup'ing multiple batchs with of the
            same recipe.

            Returns: list of dict where each dict is a option for the pico.
        """
        recipe_session = RecipeDB(
            userid=self.userid
        )
        batch_list = []

        recipes = get_recipes(self.auth)
        LOG.debug(json.dumps(recipes, indent=2))
        for batch in get_batchs(self.auth):
            name = batch['recipe']['name']
            if name not in batch_list:
                recipe_session.add_recipe(
                    recipe=_gen_pico(recipes[name])
                )
        recipe_session.save()
        return recipe_session.list_recipes()

    def get_recipe(self, _id) -> dict:
        """
            I rerturn a recipe
        """
        recipe_session = RecipeDB(
            userid=self.userid
        )
        recipe_session.load()
        return recipe_session.fetch_recipe(_id)
