""" I plot a brew based on a session log.
"""


import argparse
import json



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
    # parser.add_argument('--filename', '-c',
    #                     required=False,
    #                     default='general',
    #                     help='The channel to post the message to.')
    parser.add_argument(
        '--filename',
        default='example.json',
        nargs='*'
    )
    return parser.parse_args()


def create_graph(filename: str):
    """ I create the graph

    Args:
        filename (str): filename of the session data
    """
    count = 1
    x_axis = []
    wort_temp = []
    heat_temp = []
    drain_temp = []
    target_temp = []
    session = load_session(filename)
    for record in session['SessionLogs']:
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
    plt.xlabel(f"Events {len(session['SessionLogs'])}")
    plt.ylabel('Temperature(°F)')
    plt.title(
        f"{session['Name']} {session['CreationDate']}",
        fontsize = 20
    )
    plt.grid()
    plt.legend()
    plt.savefig('output.png')
    # plt.show()


def main():
    """ main method
    """
    args = _options()
    create_graph(args.filename)


if __name__ == '__main__':
    main()