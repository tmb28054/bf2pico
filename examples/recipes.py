"""
    Welcome to bf2picocli.

    I prompt for credentials and then use the sdk to connect to brewfather
    then convert it to pico brew steps.
"""


import argparse
import json
import logging
import os


from bf2pico import BrewFather, CACHE


LOG = logging.getLogger()


def _options() -> object:
    """
        I provide the argparse option set.

        Returns
            argparse parser object.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('--purge', '--force',
        required=False,
        dest='purge',
        action='store_true',
        default=False,
        help="Purge Cache?"
    )
    parser.add_argument('--apikey',
        required=False,
        default=os.getenv('BREWFATHER_APIKEY', ''),
        help='The API key to use when connecting to brewfather.')
    parser.add_argument('--userid',
        required=False,
        default=os.getenv('BREWFATHER_USERID', ''),
        help='The userid to use when connecting to brewfather.')
    return parser.parse_args()



def _main() -> None:
    """
        Main Logic
    """
    logging.basicConfig(level=logging.INFO)
    args = _options()

    if args.purge:
        CACHE.clear()

    recipe = BrewFather(
        userid=args.userid,
        apikey=args.apikey
    )
    print(
        json.dumps(
            recipe.pico(),
            indent=2
        )
    )

if __name__ == '__main__':
    _main()
