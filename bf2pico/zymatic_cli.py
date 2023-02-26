"""_summary_

Returns:
    _type_: _description_
"""
import argparse
import json
import textwrap


from tabulate import tabulate


from bf2pico import (
    CACHE,
    LOG,
    brewfather,
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
        choices=['add', 'update', 'delete', 'list'],
    )
    parser.add_argument('resource',
        nargs=1,
        help='what to',
        choices=['device', 'devices', 'user', 'users', 'cache'],
    )
    return parser.parse_args()


def add_user(crowd) -> None:
    """_summary_

    Args:
        crowd (_type_): _description_
    """
    user = input('Enter Brewfather User: ')
    apikey = input('Enter Brewfather ApiKey: ')
    confirm = input('Confirm that you want to proceed (type yes): ')
    if confirm.lower()[0] == 'y':
        crowd.put_user(
            username=user,
            apikey=apikey
        )
        list_user(crowd)
    else:
        LOG.info('User Skipped')


def add_device(crowd) -> None:
    """_summary_

    Args:
        crowd (_type_): _description_
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
            list_device(crowd)
        else:
            LOG.info('Device skipped as the user does not exist')
    else:
        LOG.info('Device skipped')


def list_user(crowd) -> None:
    """_summary_

    Args:
        crowd (_type_): _description_
    """
    LOG.debug(json.dumps(crowd.users, indent=2))
    LOG.info(display(crowd.users, ['User','ApiKey']))


def list_device(crowd) -> None:
    """_summary_

    Args:
        crowd (_type_): _description_
    """
    LOG.debug(json.dumps(crowd.devices, indent=2))
    LOG.info(display(crowd.devices, ['Device','User']))


def delete_user(crowd) -> None:
    """_summary_

    Args:
        crowd (_type_): _description_
    """
    user = input('Enter Brewfather User to delete: ')
    if user in crowd.users:
        if f'"{user}"' not in json.dumps(crowd.devices):
            crowd.delete_user(user)
        else:
            LOG.info('User still has devices not deleting')
    else:
        LOG.info('%s not found', user)


def delete_device(crowd) -> None:
    """_summary_

    Args:
        crowd (_type_): _description_
    """
    device = input('Enter Brewfather device to delete: ')
    if device in crowd.devices:
        crowd.delete_user(device)
    else:
        LOG.info('%s not found', device)


def list_cache(_) -> None:
    """ I display the cache as a dict

    Args:
        crowd (_type_): brewfather auth object
    """
    result = {}
    for key in list(CACHE):
        result[key] = CACHE.get(key, None)
    LOG.info(json.dumps(result, indent=2, default=str))


def display(data: dict, header: list) -> None:
    """_summary_

    Args:
        data (dict): data to disply
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
    globals()[action_resource](crowd)


if __name__ == '__main__':
    main()
