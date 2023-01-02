"""
    I am an SDK for brokering, loading recipes from brewfather, and
    transforming them into pico runbooks.

   Environment variables can be provided to bypass the requirement to
   include initialization.

    BF2PICO_CACHE: The cache time in seconds
    BREWFATHER_USERID: The userid for brewfather
    BREWFATHER_APIKEYL: The apikey for brewfather

"""


import base64
import json
import logging
import os


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


DRAINTIME = 8


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
                'drain_time': 0,
                'hop_time': '',
                'location': 'PassThru',
                'name': 'Heat Mash',
                'step_time': 0,
                'temperature': 152,
                'total_time': 0
            },
            { # Convert carbs to sugar
                'drain_time': DRAINTIME,
                'hop_time': '',
                'location': 'Mash',
                'name': 'Mash',
                'step_time': step['stepTime'],
                'temperature': celsius2fahrenheit(step['stepTemp']),
                'total_time': step['stepTime'] + DRAINTIME
            },
        ]

    # add a step to heat to a boil
    steps += [
        {
            'drain_time': 0,
            'hop_time': '',
            'location': 'PassThru',
            'name': 'Heat to Boil',
            'step_time': 0,
            'temperature': 207,
            'total_time': 0
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
                    'drain_time': 0,
                    'hop_time': '',
                    'location': 'PassThru',
                    'name': 'Pre-hop Boil',
                    'step_time': step_time,
                    'temperature': 207,
                    'total_time': step_time
                }
            ]

        # add the hops
        steps += [
            {
                'drain_time': 0,
                'hop_time': index,
                'location': f'Adjunct{slot}',
                'name': f'Hops {slot}',
                'step_time': index,
                'temperature': 207,
                'total_time': index
            },
        ]

        boil_time = index
        slot += 1

    if whirlpool:
        steps += [
            {
                'drain_time': 0,
                'hop_time': '',
                'location': 'PassThru',
                'name': 'Cool to Whirlpool',
                'step_time': 0,
                'temperature': 175,
                'total_time': 0
            },
            {
                'drain_time': 5,
                'hop_time': whirlpool,
                'location': f'Adjunct{slot}',
                'name': 'Whirlpool',
                'step_time': whirlpool,
                'temperature': 175,
                'total_time': whirlpool + 5
            },
        ]

    pico = {
        'id': recipe['_id'],
        'name': recipe['name'],
        'steps': steps
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
        return CACHE['recipes']
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

    CACHE.set('recipes', recipes, expire=CACHE_TIME)

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
        return CACHE['batchs']

    response = requests.get(
        'https://api.brewfather.app/v1/batches?limit=50&status=Brewing',
        headers={
            'Content-Type': 'json',
            'authorization': f'Basic {auth}'
        }
    )
    result = json.loads(response.text)
    CACHE.set('batchs', result, expire=CACHE_TIME)
    return result

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
