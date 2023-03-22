"""_summary_

Returns:
    _type_: _description_
"""
import argparse
import json
import sys
import textwrap


from tabulate import tabulate


from bf2pico import (
    CACHE,
    LOG,
    PARAMETER_PREFIX,
    brewfather,
    pico,
    get_parameter,
    prosaic,
)


def _options() -> object:
    """ I provide the argparse option set.

        Returns:
            argparse parser object.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('action',
        nargs=1,
        help='What to do',
        choices=['add', 'update', 'delete', 'list', 'get'],
    )
    parser.add_argument('resource',
        nargs=1,
        help='what to',
        choices=[
            'device', 'devices', 'user', 'users', 'cache', 'email', 'emails',
            'recipes', 'recipe', 'mailserver', 'mailport', 'mailfrom',
            'emaillogin', 'emailpassword'
        ],
    )
    parser.add_argument('--keys',
        required=False,
        dest='only_keys',
        action='store_true',
        default=False,
        help='for list cache only list the keys'
    )
    parser.add_argument('--cache-item',
        dest='cache_item',
        help='the item to get',
        default='',
        required=False
    )
    parser.add_argument('--device', '--device_id', '--device-id',
        dest='device_id',
        help='the device_id to get',
        default='',
        required=False
    )
    parser.add_argument('--recipe',
        dest='recipe',
        help='the recipe to get',
        default='',
        required=False
    )
    parser.add_argument('--recipe-id', '--recipe_id',
        dest='recipe_id',
        help='the recipe to get',
        default='',
        required=False
    )
    return parser.parse_args()


def add_email(crowd, _) -> None:
    """ I add a email

    Args:
        crowd (object): A object of the configured data
        _ (object): argparse object
    """
    user = input('Enter Brewfather User: ')
    email = input('Enter email: ')
    confirm = input('Confirm that you want to proceed (type yes): ')
    if confirm.lower()[0] == 'y':
        crowd.put_email(
            username=user,
            email=email
        )
        list_email(crowd, _)
    else:
        LOG.info('User Skipped')


def add_parameter(crowd, args) -> None:
    """ I add a email

    Args:
        crowd (object): A object of the configured data
        args (object): argparse object
    """
    parameter = input(f'Enter {args.resource[0]}: ')
    confirm = input('Confirm that you want to proceed (type yes): ')
    if confirm.lower()[0] == 'y':
        prosaic.put_parameter(f'{PARAMETER_PREFIX}/{args.resource[0]}', parameter)
        list_parameter(crowd, args)
    else:
        LOG.info('Skipped')


def add_user(crowd, _) -> None:
    """ add user

    Args:
        crowd (object): A object of the configured data
        _ (object): argparse object
    """
    user = input('Enter Brewfather User: ')
    apikey = input('Enter Brewfather ApiKey: ')
    confirm = input('Confirm that you want to proceed (type yes): ')
    if confirm.lower()[0] == 'y':
        crowd.put_user(
            username=user,
            apikey=apikey
        )
        list_email(crowd, _)
    else:
        LOG.info('User Skipped')


def add_device(crowd, _) -> None:
    """ add device

    Args:
        crowd (object): A object of the configured data
        _ (object): argparse object
    """
    device = input('Enter pico DeviceId: ')
    user = input('Enter Brewfather User: ')
    confirm = input('Confirm that you want to proceed (type yes): ')
    if confirm.lower()[0] == 'y':
        if user in crowd.users:
            crowd.put_device(
                device_id=device,
                username=user
            )
            list_device(crowd, _)
        else:
            LOG.info('Device skipped as the user does not exist')
    else:
        LOG.info('Device skipped')


def list_user(crowd, _) -> None:
    """ list users

    Args:
        crowd (object): A object of the configured data
        _ (object): argparse object
    """
    LOG.debug(json.dumps(crowd.users, indent=2))
    LOG.info(display(crowd.users, ['User','ApiKey']))


def list_email(crowd, _) -> None:
    """ list email

    Args:
        crowd (object): A object of the configured data
        _ (object): argparse object
    """
    LOG.debug(json.dumps(crowd.emails, indent=2))
    LOG.info(display(crowd.emails, ['User','emails']))


def list_parameter(_, args) -> None:
    """ list parameter

    Args:
        _ (object): A object of the configured data
        args (object): argparse object
    """
    value = get_parameter(f'{PARAMETER_PREFIX}/{args.resource[0]}')
    LOG.debug('%s = "%s"', args.resource[0], value)
    LOG.info(display({args.resource[0]: value}, ['Key','Value']))


def list_device(crowd, _) -> None:
    """ list devices

    Args:
        crowd (object): A object of the configured data
        _ (object): argparse object
    """
    LOG.debug(json.dumps(crowd.devices, indent=2))
    LOG.info(display(crowd.devices, ['Device','User']))


def delete_user(crowd, _) -> None:
    """ delete a user

    Args:
        crowd (object): A object of the configured data
        _ (object): argparse object
    """
    user = input('Enter Brewfather User to delete: ')
    if user in crowd.users:
        if f'"{user}"' not in json.dumps(crowd.devices):
            crowd.delete_user(user)
        else:
            LOG.info('User still has devices not deleting')
    else:
        LOG.info('%s not found', user)


def delete_device(crowd, _) -> None:
    """ delete a device

    Args:
        crowd (object): A object of the configured data
        _ (object): argparse object
    """
    device = input('Enter Brewfather device to delete: ')
    if device in crowd.devices:
        crowd.delete_user(device)
    else:
        LOG.info('%s not found', device)


def get_cache(_, args) -> None:
    """ I display the cache as a dict

    Args:
        _ (object): A object of the configured data
        args (object): argparse object
    """
    if not args.cache_item:
        LOG.info('what key to get')
        list_cache(_, args)
    else:
        result_data = CACHE.get(args.cache_item, '')
        try:
            result_json = json.loads(result_data)
            result_data = json.dumps(result_json, indent=2)
        except:  # pylint: disable=bare-except
            pass
        LOG.info(result_data)


def list_cache(_, args) -> None:
    """ I display the cache as a dict

    Args:
        _ (object): A object of the configured data
        args (object): argparse object
    """
    if args.only_keys:
        result = []
        for key in CACHE:
            result.append([key])
        LOG.info(
            tabulate(
                result,
                ['keys'],
                tablefmt="grid"
            )
        )
    else:
        result = {}
        for key in list(CACHE):
            result[key] = CACHE.get(key, None)
        LOG.info(json.dumps(result, indent=2, default=str))


def list_recipe(_, args) -> None:
    """ I display the recipes for all users

    Args:
        _ (object): A object of the configured data
        args (object): argparse object
    """
    if not args.device_id:
        LOG.info('No device_id provided')
        sys.exit(1)
    result = {}
    creds = brewfather.BrewAuth(device_id=args.device_id)
    for recipe in pico.list_recipes(creds):
        result[recipe['ID']] = recipe['Name']
    LOG.info(display(result, ['ID','recipe']))


def get_recipe(_, args) -> None:
    """ I display the recipes for all users

    Args:
        _ (object): A object of the configured data
        args (object): argparse object
    """
    if not args.device_id:
        LOG.info('No device_id provided')
        sys.exit(1)
    if not args.recipe_id:
        LOG.info('No recipe provided')
        sys.exit(1)
    creds = brewfather.BrewAuth(device_id=args.device_id)
    recipe = pico.get_recipe(creds, args.recipe_id)
    LOG.info(json.dumps(recipe, indent=2))


def display(data, header: list) -> None:
    """_summary_

    Args:
        data (dict, list): data to disply
        header (list): column headers
    """
    result = []
    for key, value in data.items():
        result.append(
            [
                key,
                textwrap.fill(value, 40)
            ]
        )
    LOG.info(
        tabulate(
            result,
            header,
            tablefmt="grid"
        )
    )


def main():
    """ main method
    """
    args = _options()
    crowd = brewfather.BrewFatherUsers()
    resource = args.resource[0]
    if resource.endswith('s'):
        resource = resource[:-1]
    action = args.action[0]
    if action == 'update':
        action = 'add'
    action_resource = f'{action}_{resource}'
    if 'mail' in resource:
        if action == 'get':
            action = 'list'
        action_resource = f'{action}_parameter'
    try:
        globals()[action_resource](crowd, args)
    except KeyError as _:
        LOG.info('Unsupported Resource (%s) for %s', args.resource[0], args.action[0])


if __name__ == '__main__':
    main()
