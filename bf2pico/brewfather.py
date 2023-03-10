"""
    I provide the brewfather logic
"""

import base64
import json
import os
import requests


from bf2pico import (
    CACHE,
    CACHE_TIME,
    LOG,
    PARAMETER_PREFIX,
    REQUESTS_TIMEOUT,
    pico,
    prosaic,
)


STATUS_OPTIONS = {
    'planning': 'Planning',
    'fermenting': 'Fermenting',
    'brewing': 'Brewing',
}


def get_batchs(auth: str, status='Planning') -> dict:
    """
        I get a list of batchs which are marked for brewing in brewfather

        Args
            auth: the base64 auth string

        Returns: List of dict representing the a batch marked for brewing
                    in brewfather
    """
    status = status.lower()
    if status not in STATUS_OPTIONS:
        raise ValueError('Status not valid')

    status = STATUS_OPTIONS.get(status, None)

    cache_key = f'{auth}-{status}-batchs'

    if cache_key in CACHE:
        return CACHE[cache_key]

    response = requests.get(
        'https://api.brewfather.app/v2/batches?limit=50&status=Planning',
        timeout=REQUESTS_TIMEOUT,
        headers={
            'Content-Type': 'json',
            'authorization': f'Basic {auth}'
        }
    )
    LOG.debug('status code = %s', response.status_code)
    LOG.debug('text = %s', response.text)
    result = json.loads(response.text)
    CACHE.set(cache_key, result, expire=CACHE_TIME)
    return result


def get_recipe(auth: str, recipe_id: str) -> dict:
    """ Get the Brewfather recipe

    Args:
        auth (str): The API Authentication string
        recipe_id (str): The Brewfather recipe id

    Returns:
        dict: _description_
    """
    recipe_key = f'recipe-{recipe_id}'
    recipe = CACHE.get(recipe_key, {})
    if recipe:
        return recipe

    url = f'https://api.brewfather.app/v2/recipes/{recipe_id}'
    response = requests.get(
        url,
        timeout=REQUESTS_TIMEOUT,
        headers={
            'Content-Type': 'json',
            'authorization': f'Basic {auth}'
        }
    )
    LOG.debug('get recipe return code is %s', response.status_code)
    LOG.debug('get recipe text is %s', response.text)
    return json.loads(response.text)


def get_recipes(auth) -> dict:
    """
        I get the all recipes from brewfather.

        Args
            auth: the base64 auth string

        Returns: Dict of recipes with the key being the recipe name
                    and the value being the brewfather recipe.
    """
    records_per_call = 50
    recipe_key = f'{auth}-recipes'
    recipes = CACHE.get(recipe_key, {})
    if recipes:
        return recipes

    url = f'https://api.brewfather.app/v2/recipes?limit={records_per_call}'
    response = requests.get(
        url,
        timeout=REQUESTS_TIMEOUT,
        headers={
            'Content-Type': 'json',
            'authorization': f'Basic {auth}'
        }
    )
    LOG.debug('get recipes return code is %s', response.status_code)
    LOG.debug('get recipes text is %s', response.text)

    loop_count = 0
    while True:
        count = 1
        for recipe in json.loads(response.text):
            recipes[recipe['name']] = recipe
            count += 1
        if count < records_per_call:
            break
        loop_count += 1
        response = requests.get(
            f'{url}&start_after={loop_count * records_per_call}',
            timeout=REQUESTS_TIMEOUT,
        )
        LOG.debug('get recipes return code is %s', response.status_code)
        LOG.debug('get recipes text is %s', response.text)

    CACHE.set(f'{auth}recipes', recipes, expire=CACHE_TIME)

    return recipes


def get_batch_recipe_map(user_id: str) -> dict:
    """_summary_

    Args:
        user_id (str): _description_

    Returns:
        dict: _description_
    """
    result_key = f'planning_recipe_map/{user_id}.json'
    result = prosaic.s3_get(result_key, {})
    if result:
        result = json.loads(result)
    return result


def get_planning_recipe_map(user_id: str, planning: list, recipes: dict) -> dict:
    """ I return the persistent map of planning to recipe

    Args:
        planning (list): List of planned brews
            [
                {
                    "_id": id,
                    "batchNo": 9,
                    "brewDate": 1677387600000,
                    "brewer": null,
                    "name": "Batch",
                    "recipe": {
                        "name": Name
                    },
                    "status": "Planning"
                },
            ]
        recipes (dict): dict of brewfather recipes
            {
                "Ginger Beer": {
                    "_id": "1SmDxbEKjNUciy9wYzijlzUYmVIyqs",
                    "author": "Topaz",
                    "equipment": {
                        "name": "Default"
                    },
                    "name": "Ginger Beer",
                    "type": "Extract"
                }
            }
    Returns:
        dict: batch_id to recipe_id
            {
                batch_id: recipe_id
            }
    """
    result =  get_batch_recipe_map(user_id)
    for recipe in planning:
        if recipe['_id'] not in result:
            if recipe['recipe']['name'] not in recipes:
                raise ValueError('Recipe not in Recipes')
            result[recipe['_id']] = \
                recipes[recipe['recipe']['name']]['_id']

    result_key = f'planning_recipe_map/{user_id}.json'
    prosaic.s3_put(json.dumps(result), result_key)
    return result


def get_recipe_from_batch_id(creds: object, batch_id: str) -> dict:
    """ I return the brewfather recipe for a given batch_id

    Args:
        creds (object): The auth object for brewfather
        batch_id (str): string fo the batch id

    Returns:
        dict: brewfather dict of the recipe
    """
    # batch_recipe_map =  get_batch_recipe_map(creds.user_id)
    recipe_map = pico.get_list_recipes_map(creds.user_id)
    LOG.debug('batch_id is %s', batch_id)
    LOG.debug('recipe_map')
    LOG.debug(json.dumps(recipe_map, indent=2))
    recipe_id = recipe_map['by_batch_id'].get(batch_id, {'recipe_id': None})['recipe_id']
    LOG.debug('recipe_id is %s', str(recipe_id))
    if not recipe_id:
        LOG.info('Unable to find recipe from batch')
        raise Exception('batch_id not in batch_recipe_map')  # pylint: disable=broad-exception-raised
    return get_recipe(creds.auth(), recipe_id)


def change_batch_status(creds: object, batch_id: str, status: str) -> None:
    """ I update the batch to brewing

    Args:
        creds (object): a brewfather credential object
        batch_id (str): the batch to update
        status (str): the new status either (planning, brewing, or fermenting)
        _id (str): _description_
    """
    status_options = {
        'planning': 'Planning',
        'fermenting': 'Fermenting',
        'brewing': 'Brewing'
    }
    new_status = status_options[status.lower()]
    url = f'https://api.brewfather.app/v2/batches/{batch_id}?status={new_status}'
    response = requests.patch(
        url,
        data={
            'status': new_status,
        },
        timeout=REQUESTS_TIMEOUT,
        headers={
            'Content-Type': 'json',
            'authorization': f'Basic {creds.auth()}'
        }
    )
    LOG.debug(response.status_code)
    LOG.debug(response.text)


def update_brgewlog(creds, name: str, comment: str) -> None:
    """ I publish to the brewfather brew log

    Args:
        user_id (str): the user_id
        device_id (str): the device_id
        comment (str): the comment to add
        name (str): the beer name
    """
    response = requests.post(
        "https://log.brewfather.net/stream?id=bVqW9nk4Pz3ro0",
        headers={
            'Content-Type': 'application/json',
            'authorization': f'Basic {creds.auth()}'
        },
        timeout=REQUESTS_TIMEOUT,
        json={
            'name': 'bf2pico',
            "temp": 20.32,
            'beer': name,
            'comment':  comment
        }
    )
    LOG.debug(response.status_code)
    LOG.debug(response.text)


class BrewFatherUsers:
    """ I provide an object to interface with the stored brewfather
        api users, apikeys and pico devices
    """
    def __init__(self) -> object:
        """ I initialize the brewfather api users object

        Providers:
            users: a dict of brewfather api users to api key
            devices: a dict of pico device to brewfather user

        Returns:
            object: brewfather users object
        """
        self.users = prosaic.get_parameters(f'{PARAMETER_PREFIX}/users/')
        self.devices = prosaic.get_parameters(f'{PARAMETER_PREFIX}/devices/')
        self.emails = prosaic.get_parameters(f'{PARAMETER_PREFIX}/emails/')

    def put_user(self, **kwarg) -> None:
        """ I add a parameter with user and apikey

        kwarg:
            username (str): _description_
            apikey (str): _description_
        """
        username = kwarg.get('username', '')
        apikey = kwarg.get('apikey', '')
        if username and apikey:
            prosaic.put_parameter(f'{PARAMETER_PREFIX}/users/{username}', apikey)
            self.users[username] = apikey
        else:
            raise Exception('Both username and apikey required')  # pylint: disable=broad-exception-raised

    def put_email(self, **kwarg) -> None:
        """ I add a parameter with user and apikey

        kwarg:
            username (str): brewfather user_id
            email (str): email address to send notifications.
        """
        username = kwarg.get('username', '')
        email = kwarg.get('email', '')
        if username and email:
            prosaic.put_parameter(f'{PARAMETER_PREFIX}/emails/{username}', email)
            self.emails[username] = email
        else:
            raise Exception('Both username and email required')  # pylint: disable=broad-exception-raised

    def delete_user(self, username: str) -> None:
        """ I delete a brewfather user

        Args:
            username (str): the api user to delete
        """
        prosaic.delete_parameter(f'{PARAMETER_PREFIX}/users/{username}')
        self.users.pop(username)

    def put_device(self, **kwarg) -> None:
        """ I add a device which is linked to a brewfather api user

        kwarg:
            username (str): brewfather api user
            device_id (str): pico device id
        """
        username = kwarg.get('username', '')
        device_id = kwarg.get('device_id', '')
        if username in self.users:
            prosaic.put_parameter(f'{PARAMETER_PREFIX}/devices/{device_id}', username)
            self.devices[device_id] = username
        else:
            raise Exception('user does not exist')  # pylint: disable=broad-exception-raised

    def delete_device(self, device_id: str) -> None:
        """ I provide ability to delete a device

        Args:
            device_id (str): pico device
        """
        prosaic.delete_parameter(f'{PARAMETER_PREFIX}/devices/{device_id}')
        self.users.pop(device_id)

    def delete_email(self, user_id: str) -> None:
        """ I provide ability to delete a device

        Args:
            user_id (str): the brewfather user_id to add the email too.
        """
        prosaic.delete_parameter(f'{PARAMETER_PREFIX}/email/{user_id}')
        self.emails.pop(user_id)


class BrewAuth:  # pylint: disable=too-few-public-methods
    """
        I manage the session of a brew event.

        Requires one of the following:
            - device_id: string of the zymatic token
            - user_id: string of the brewfather userid
            - user_id and api_key: string of the brewfather user_id and api_key
            - Environment Variable BREWFATHER_DEFAULT_DEVIDE: aka device_id
            - Environment Variable BREWFATHER_USERID: aka device_id

    """
    def __init__(self, **kwargs) -> object:
        """ I am the init to a brew log
        """
        self.logger = LOG
        self.logger.debug('Creating BrewAuth')

        self.crowd = BrewFatherUsers()

        self.device_id = kwargs.get(
            'device_id',
            os.getenv(
                'BREWFATHER_DEFAULT_DEVIDE',
                None
            )
        )

        # Return the Environment Override or lookup from device_id
        self.user_id = kwargs.get(
            'user_id',
            self.crowd.devices.get(
                self.device_id,
                os.getenv(
                    'BREWFATHER_USERID',
                    ''
                )
            )
        )
        if not self.user_id:
            raise Exception('No user_id')  # pylint: disable=broad-exception-raised

        self.api_key = kwargs.get(
            'api_key',
            self.crowd.users.get(
                self.user_id,
                ''
            )
        )
        if not self.api_key:
            raise Exception('No api_key')  # pylint: disable=broad-exception-raised

    def auth(self) -> str:
        """ Return the auth string for calling the brewfather api

        Returns:
            str: the brewfather authentication string
        """
        auth_str = f'{self.user_id}:{self.api_key}'
        LOG.debug('pre-base64 %s', auth_str)
        result = base64.b64encode(auth_str.encode('ascii')).decode('utf-8')
        LOG.debug('post-base64 %s', result)
        return result
