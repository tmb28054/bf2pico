""" I plot a brew based on a session log.
"""


import argparse
import json
# import sys
import time


import matplotlib.pyplot as plt


def load_session(filename: str) -> dict:
    """ Load the session file

    Args:
        filename (str): File containing the session file

    Returns:
        dict: dict of the session
    """
    with open(filename, 'r', encoding='utf8') as handler:
        return json.load(handler)


def celsius_to_fahrenheit(temp: float) -> float:
    """_summary_

    Args:
        temp (float): _description_

    Returns:
        float: _description_
    """
    return temp * 1.8 + 32


def _options() -> object:
    """ I provide the argparse option set.

        Returns
            argparse parser object.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--filename', '-f',
        default='example.json',
        help='the file to plot'
    )
    parser.add_argument(
        '--save', '-s',
        default='',
        help='the file to plot'
    )
    return parser.parse_args()


def create_graph(data: dict, filename: str):
    """ I create the graph

    Args:
        data: dict of the session data
        filename: the file to write the graph.
    """
    count = 1
    x_axis = []
    wort_temp = []
    heat_temp = []
    drain_temp = []
    target_temp = []

    for record in data.get('SessionLogs', []):
        x_axis.append(count)
        wort_temp.append(celsius_to_fahrenheit(record['WortTemp']))
        heat_temp.append(celsius_to_fahrenheit(record['ThermoBlockTemp']))
        drain_temp.append(celsius_to_fahrenheit(record['DrainTemp']))
        target_temp.append(celsius_to_fahrenheit(record['TargetTemp']))
        count += 1

    plt.plot(x_axis, wort_temp, color = 'g', linestyle = 'solid',
            marker = 'o',label = "Wort Temp")
    plt.plot(x_axis, heat_temp, color = 'r', linestyle = 'solid',
            marker = 'o',label = "Heat Temp")
    plt.plot(x_axis, drain_temp, color = 'b', linestyle = 'solid',
            marker = 'o',label = "Drain Temp")
    plt.plot(x_axis, target_temp, color = 'y', linestyle = 'solid',
            marker = 'o',label = "Target Temp")

    plt.xticks(rotation = 25)
    plt.ylabel('Temperature(°F)')
    try:
        name = data.get('Name', 'unknown')
        start_epoch = data['SessionLogs'][0]['epoch']
        start_time = time.strftime('%H:%M', time.localtime(start_epoch))
        stop_epoch = data['SessionLogs'][len(data['SessionLogs']) -1]['epoch']
        stop_time = time.strftime('%H:%M', time.localtime(stop_epoch))
        brew_date = time.strftime('%Y-%m', time.localtime(start_epoch))
    except:  # pylint: disable=bare-except
        print('Brewplot failure')
        print(json.dumps(data, indnet=2))
        # sys.exit(1)
    plt.xlabel(f'{brew_date} {start_time} - {stop_time}')
    plt.title(
        name,
        fontsize = 20
    )
    plt.grid()
    plt.legend()
    if filename:
        plt.savefig(filename)
    else:
        plt.show()


def main():
    """ main method
    """
    args = _options()
    data = load_session(args.filename)
    create_graph(data, args.save)


if __name__ == '__main__':
    main()
