""" I provide the pico logic

"""


import json
import random
import string


from bf2pico import (
    CACHE,
    LOG,
    PERSISTENT_CACHE_TIME,
    brewfather,
    prosaic,
)


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
DRAINTIME = 8  # how long the zymatic should drain



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


def _fix_noboil(steps: list) -> list:
    """ I fix the noboil bug

    Args:
        steps (list): list of pico brew steps

    Returns:
        list: list of pico brew steps
    """
    last_record = len(steps) - 1
    if steps[last_record]['Name'] == 'Heat to Boil':
        del steps[last_record]
    return steps


def _fix_mash(steps: list) -> list:
    """ I fix a brew recipe that boils without a mash

    Args:
        steps (list): list of pico brew steps

    Returns:
        list: list of pico brew steps
    """
    if steps[0]['Name'] == 'Heat Mash' and steps[1]['Name'] == 'Mash' \
            and steps[1]['Time'] == 0:
        del steps[0]
        del steps[0]
    return steps


def _chill_patch(recipe: dict) -> list:
    """ I return the chill steps if the recipe calls for it

    Args:
        recipe (dict): Dict of the BrewFather Recipe

    Returns:
        list: List of pico steps to chill
    """
    result = []
    for record in recipe.get('miscs', []):
        if record['name'].lower() == 'chill':
            result = [
                {
                    "Name": "Connect Chiller",
                    "Temp": 52,
                    "Time": 0,
                    "Location": 6,
                    "Drain": 0
                },
                {
                    "Name": "Chill",
                    "Temp": record['amount'],
                    "Time": record['time'],
                    "Location": 0,
                    "Drain": 10
                }
            ]
    return result


def gen_pico(recipe: dict) -> dict:
    """
        I generate a pico run plan from a brewfather recipe.

        Args
            recipe: A recipe from brewfather in dict form.

        Returns: A pico list of steps to brew the recipe.
    """

    steps = []
    whirlpool = 0
    chill = _chill_patch(recipe)

    # build the mash steps
    for step in recipe['mash']['steps']:
        steps += [
            { # Raise the water temp
                'Drain':  0,
                'Location': PICO_LOCATIONS.get('PassThru', 0),
                'Name': 'Heat Mash',
                'Time': 0,
                'Temp': celsius2fahrenheit(step['stepTemp']),
            },
            { # Convert carbs to sugar
                'Drain':  DRAINTIME,
                'Location': PICO_LOCATIONS.get('Mash', 0),
                'Name': 'Mash',
                'Time': step['stepTime'],
                'Temp': celsius2fahrenheit(step['stepTemp']),
            },
        ]

    # add a step to heat to a boil
    steps += [
        {
            'Drain':  0,
            'Location': PICO_LOCATIONS.get('PassThru', 0),
            'Name': 'Heat to Boil',
            'Time': 0,
            'Temp': 207,
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
    total_hop_time = 0
    for hop in sorted(hops):
        adj_hob = hop - total_hop_time
        total_hop_time = hop
        adjusted_hops.append(adj_hob)

    # do we boil before our first hop?
    if total_hop_time < boil_time:
        steps += [
            {
                'Drain':  0,
                'Location': PICO_LOCATIONS.get('PassThru', 0),
                'Name': 'Pre-hop Boil',
                'Time': boil_time - total_hop_time,
                'Temp': 207,
            }
        ]

   # run the hops in order they should be added
    slot = 1
    for index in reversed(adjusted_hops):
        if boil_time < index:
            LOG.info('boil time less then hop time, adjusting boil time to %s', index)
            boil_time = index


        # add the hops
        steps += [
            {
                'Drain':  0,
                'Location': PICO_LOCATIONS.get(f'Adjunct{slot}', 0),
                'Name': f'Hops {slot}',
                'Time': index,
                'Temp': 207,
            },
        ]

        boil_time = index
        slot += 1

    if whirlpool:
        steps += [
            {
                'Drain':  0,
                'Location': PICO_LOCATIONS.get('PassThru', 0),
                'Name': 'Cool to Whirlpool',
                'Time': 0,
                'Temp': 175,
            },
            {
                'Drain':  5,
                'Location': PICO_LOCATIONS.get(f'Adjunct{slot}', 0),
                'Name': 'Whirlpool',
                'Time': whirlpool,
                'Temp': 175,
            },
        ]

    steps = \
        _fix_noboil(
            _fix_mash(
                steps
            )
        )

    if chill:
        steps += chill

    pico = {
        'ID': recipe['_id'],
        'Name': recipe['name'],
        'StartWater': 16.69,
        'TypeCode': 'Beer',
        'Steps': steps
    }
    return pico


def get_list_recipes_map(user_id: str) -> dict:
    """_summary_

    Args:
        user_id (str): brewfather user id

    Returns:
        dict: dict of the list_recipes
            {
                'by_pico_id': {
                    170335: {
                        name: name,
                        batch_id: the_unique_batch_id,
                        recipe_id: recipe_id
                    }
                }
                'by_name': {
                    name: {
                        pico_id: pico_id,
                        batch_id: the_unique_batch_id,
                        recipe_id: recipe_id
                    }
                },
                'by_batch_id': {
                    batch_id: {
                        name: name,
                        pico_id: pico_id,
                        recipe_id: recipe_id
                    }
                },
                'by_recpie_id': {
                    recipe_id: {
                        name: name,
                        pico_id: pico_id,
                        batch_id: the_unique_batch_id
                    }
                }
            }
    """
    result_key = f'pico_recipe_map/{user_id}.json'
    result = prosaic.s3_get(result_key, None)
    if result:
        return json.loads(result)
    return \
        {
            'by_pico_id': {},
            'by_name': {},
            'by_batch_id': {},
            'by_recipe_id': {},
        }


def list_recipes_next_id(data: dict) -> int:
    """ I return the next id to be used

    Args:
        data (dict): dict of our pico_iud to batch ids.

    Returns:
        int: next int to use
    """
    if not data:
        return 170335
    return int(max(list(data))) + 1


def add_list_recipes(user_id: str, data: dict, recipe:dict) -> dict:
    """ I add a new recipe to the list recipes map

    Args:
        user_id (str): string of the brewfather user_id
        data (dict): dict of the recipes_map
            {
                'by_pico_id': {
                    170335: {
                        name: name,
                        batch_id: the_unique_batch_id,
                        recipe_id: recipe_id
                    }
                }
                'by_name': {
                    name: {
                        pico_id: pico_id,
                        batch_id: the_unique_batch_id,
                        recipe_id: recipe_id
                    }
                },
                'by_batch_id': {
                    batch_id: {
                        name: name,
                        pico_id: pico_id,
                        recipe_id: recipe_id
                    }
                },
                'by_recpie_id': {
                    recipe_id: {
                        name: name,
                        pico_id: pico_id,
                        batch_id: the_unique_batch_id
                    }
                }
            }
        recipe (dict): the recipe to add
            {
                "_id": "ydnH0UmnH45Zf40Cg9VvQQ3X4Nyo16",
                "batchNo": 8,
                "brewDate": 1676782800000,
                "brewer": null,
                "name": "Batch",
                "recipe": {
                    "name": "Heat to 110"
                },
                "status": "Planning"
            }

    Returns (dict): recipe map
        {
            'by_pico_id': {
                170335: {
                    name: name,
                    batch_id: the_unique_batch_id,
                    recipe_id: recipe_id
                }
            }
            'by_name': {
                name: {
                    pico_id: pico_id,
                    batch_id: the_unique_batch_id,
                    recipe_id: recipe_id
                }
            },
            'by_batch_id': {
                batch_id: {
                    name: name,
                    pico_id: pico_id,
                    recipe_id: recipe_id
                }
            },
            'by_recpie_id': {
                recipe_id: {
                    name: name,
                    pico_id: pico_id,
                    batch_id: the_unique_batch_id
                }
            }
        }
    """
    pico_id = list_recipes_next_id(data['by_pico_id'])
    batch_id = recipe['_id']
    name = recipe['recipe']['name']
    recipe_id = recipe['recipe_id']
    data['by_pico_id'][pico_id] = {
        'name': name,
        'batch_id': batch_id,
        'recipe_id': recipe_id,
    }
    data['by_name'][name] = {
        'pico_id': pico_id,
        'batch_id': batch_id,
        'recipe_id': recipe_id,
    }
    data['by_batch_id'][batch_id] = {
        'name': name,
        'pico_id': pico_id,
        'recipe_id': recipe_id
    }
    data['by_recipe_id'][recipe_id] = {
        'name': name,
        'pico_id': pico_id,
        'batch_id': batch_id,
    }
    result_key = f'pico_recipe_map/{user_id}.json'
    prosaic.s3_put(json.dumps(data), result_key)
    return data


def list_recipes(creds: object) -> list:
    """ returns a list of pico recipes

    Args:
        auth (BrewAuth): BrewAuth object for managing authentication

    Returns:
        list: Pico format list of recipes
                [
                    {
                        'ID': _id,
                        'Name': name,
                        'Kind': 0,
                        'Uri': None,
                        'Abv': -1,
                        'Ibu': -1
                    }
                ]
    """
    recipes = brewfather.get_recipes(creds.auth())
    planning = brewfather.get_batchs(creds.auth(), 'Planning')
    LOG.debug('planning')
    LOG.debug(json.dumps(planning, indent=2))
    result = []
    recipe_map = get_list_recipes_map(creds.user_id)
    LOG.debug('recipe_map')
    LOG.debug(json.dumps(recipe_map, indent=2))
    for recipe in planning:
        recipe_name = recipe['recipe']['name']
        recipe['recipe_id'] = recipes[recipe_name]['_id']
        if recipe['_id'] not in recipe_map['by_batch_id']:
            recipe_map = add_list_recipes(creds.user_id, recipe_map, recipe)
        result.append(
            {
                'ID': recipe_map['by_batch_id'][recipe['_id']]['pico_id'],
                'Name': recipe['recipe']['name'],
                'Kind': 0,
                'Uri': None,
                'Abv': -1,
                'Ibu': -1
            }
        )
    return result


def get_recipe(creds: object, pico_id: str) -> dict:
    """_summary_

    Args:
        creds (object): the authentication objects for brewfather
        pico_id (str): The string of the unique id for the recipe to fetch.

    Returns:
        dict: Pico formated brew steps.
    """
    recipe_map = get_list_recipes_map(creds.user_id)
    batch_id = recipe_map['by_pico_id'][str(pico_id)]['batch_id']
    bf_recipe = brewfather.get_recipe_from_batch_id(creds, batch_id)

    CACHE.set(
        f'{creds.device_id}-recipe',
        pico_id,
        expire=PERSISTENT_CACHE_TIME
    )

    result = gen_pico(bf_recipe)
    result['ID'] = pico_id
    return result


def change_batch_state(creds: object, pico_id: str, status: str) -> None:
    """ I update the batch status in brewfather

    Args:
        creds (object): brewfather auth object
        pico_id (str): the pico id for the batch
        status (str): string of the new status
    """

    # Move from planning to brewing
    session_map = get_list_recipes_map(creds.user_id)
    LOG.debug('session_map')
    LOG.debug(json.dumps(session_map, indent=2))
    try:
        batch_id = session_map['by_pico_id'][str(pico_id)]['batch_id']
        brewfather.change_batch_status(creds, batch_id, status)
    except:  # pylint: disable=bare-except
        LOG.debug('Unable to link to brewfather most likely a rinse.  pico_id=%s')
