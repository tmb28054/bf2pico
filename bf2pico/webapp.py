#!/usr/bin/env python
"""
    I log and broker the connection to picobrew
"""


import json
import os
import uuid

from flask import Flask, request


from bf2pico import (
    brewfather,
    pico,
    session,
)



app = Flask(__name__)


def _save(data: dict) -> None:
    """
        I save the request and response.
    """
    filename = f'data/{str(uuid.uuid4())}.json'

    if not os.path.exists('data'):
        os.makedirs('data')

    with open(filename, 'w', encoding='utf8') as handler:
        handler.write(
            json.dumps(data, indent=2)
        )


def zstate():
    """
        I return the zstate

    Returns:
           dict: what the z is looking for
    """
    return {
        'IsUpdated': True,
        'IsRegistered': True,
        'TokenExpired': False,
        'UpdateAddress': '-1',
        'RegistrationToken': '-1',
        'BoilerType': 0,
        'CurrentFirmware': '0.0.116',
        'UpdateToFirmware': None,
        'ProgramUri': None,
        'Alias': 'ZSeries',
        'SessionStats': {
            'DirtySessionsSinceClean': 1,
            'LastSessionType': 0,
            'ResumableSessionID': -1
        },
        'ZBackendError': 0
    }


@app.route('/Vendors/input.cshtml', methods=['PUT'])
def run_put():
    """
       I am the put method
    """
    params = dict(request.args)

    try:
        data = json.loads(request.data.decode('utf-8'))
    except:  # pylint: disable=bare-except
        data = {}

    if params.get('type', 'unknown') == 'ZState':
        result = zstate()

    elif params.get('type', 'unknown') == 'ZSession':
        result = zsession(params['token'], data)

    else:
        result = {
            'method': 'PUT',
            'response': {
                'params': params,
                'data': data
            },
            'code': 404
        }
    _save(result)
    return result


def list_recipes(token: str):
    """_summary_

    Args:
        token (string): _description_

    Returns:
        _type_: _description_
    """
    creds = brewfather.BrewAuth(device_id=token)
    recipe_list = pico.list_recipes(creds)
    return \
        {
            'Kind': 1,
            'Offset': 0,
            'SearchString': None,
            'MaxCount': 0,
            'TotalResults': len(recipe_list),
            'Recipes': recipe_list
        }


def zsession(token: str, request_data: dict) -> dict:
    """_summary_
        The session controller

    Args:
        token (str): _description_

    Returns:
        _type_: _description_
    """
    req_data = {}
    populate_keys = ['SessionType', 'ZProgramId', 'FirmwareVersion', 'Name',
        'DurationSec', 'MaxTemp']

    for key in populate_keys:
        req_data[key] = request_data[key]

    local_session = session.BrewLog(
        data=req_data,
        device_id=token
    )
    local_session.save()

    return local_session.data


def zsession_log(token: str, request_data: dict) -> dict:
    """_summary_
        The session controller

    Args:
        token (str): _description_

    Returns:
        _type_: _description_
    """
    local_session = session.BrewLog(
        _id=request_data['ZSessionID'],
        device_id=token
    )
    result = local_session.add_logs(request_data)
    local_session.save()

    return result


@app.route('/Vendors/input.cshtml', methods=['POST'])
def run_post():
    """ I run the post for input.cshtml

    Returns:
        response from post
    """
    params = dict(request.args)

    try:
        data = json.loads(request.data.decode('utf-8'))
    except:  # pylint: disable=bare-except
        data = {}

    if params.get('ctl', 'unknown') == 'RecipeRefListController':
        result = list_recipes(params['token'])

    elif params.get('type', 'unknown') == 'ZSession':
        result = zsession(params['token'], data)

    elif params.get('type', 'unknown') == 'ZSessionLog':
        result = zsession_log(params['token'], data)

    else:
        result = {
            'method': 'POST',
            'response': {
                'params': params,
                'data': data
            },
            'code': 404
        }
    _save(result)

    return result


def get_recipe(token:str, _id:int):
    """_summary_

    Args:
        token (str): _description_
        id (int): _description_

    Returns:
        _type_: _description_
    """
    creds = brewfather.BrewAuth(device_id=token)
    return pico.get_recipe(creds, _id)


@app.route('/Vendors/input.cshtml', methods=['GET'])
def run_get():
    """ I run the post for input.cshtml

    Returns:
        response from post
    """
    params = dict(request.args)
    try:
        data = json.loads(request.data.decode('utf-8'))
    except:  # pylint: disable=bare-except
        data = {}

    if params.get('type', 'unknown') == 'Recipe':
        return get_recipe(params['token'], int(params['id']))

    result = {
        'response': {
        'method': 'GET',
            'params': params,
            'data': data
        },
        'code': 404
    }
    _save(result)
    return result


@app.route('/health', methods=['GET'])
def health():
    """ health """
    return 'healthy'


if __name__ == "__main__":
    app.run(host='0.0.0.0')
