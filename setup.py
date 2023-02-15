#!/usr/bin/env python
"""
    I provide a package setup for the egg.
"""


from setuptools import setup


def load_project() -> dict:
    """
        I load the project.yaml file and return a dictionary for the contents.

        Args
        None

        Returns
        dict: the dictionary from the project.yaml file.

        Raises
        None
    """
    results = {}
    with open('project.yaml', 'r', encoding='utf8') as file_handler:
        data = file_handler.read()
    for line in data.split("\n"):
        if ':' in line:
            hold = line.split(':')
            key = hold[0].strip()
            value = hold[1].strip()
            results[key] = value
    return results


def get_changelog() -> str:
    """
        I return the version from changelog.

        Args
        None

        Returns
        str: string form of the current verion.
    """
    with open('CHANGELOG.md', 'r', encoding='utf8') as file_handler:
        for line in file_handler:
            if line.startswith('## ['):
                if 'unreleased' not in line.lower():
                    left = line.split(']')[0]
                    return left.split('[')[1]
    return 'unknown'


def get_readme() -> str:
    """
        Load the readme.
    """
    with open('README.md', 'r', encoding='utf8') as file_handler:
        return file_handler.read()


def get_requirements() -> list:
    """
        I generate a list of requirements from the requirements.txt
    """
    with open('requirements.txt', encoding='utf8') as file_handler:
        return file_handler.read().split("\n")


PROJECT = load_project()
setup_options = dict(
    description='Convert Brewfather Recipes to Pico Brew Steps',
    long_description=get_readme(),
    long_description_content_type='text/markdown',
    license='Apache License 2.0',
    url='https://github.com/tmb28054/cftcli',
    name=PROJECT['PyPackageName'],
    version=get_changelog(),
    author=PROJECT['Owner'],
    author_email=PROJECT['OwnerEmail'],
    scripts=[],
    package_data={
        PROJECT['PyPackageName']: []
    },
    packages=[PROJECT['PyPackageName']],
    include_package_data=True,
    install_requires=get_requirements(),
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
    ],
    entry_points={
        'console_scripts': [
            'brewplot = bf2pico.brewplot:main',
            'events = bf2pico.events:main',
        ]
    },
)

setup(**setup_options)
