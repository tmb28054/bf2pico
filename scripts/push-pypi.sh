#!/bin/bash

set -e

source ~/common/bin/activate

# build wheel
python setup.py bdist_wheel

if [ "${CI_COMMIT_BRANCH}" == "main" ]; then
    source ~/common/bin/activate
    twine upload -r pypi --skip-existing dist/*
fi
