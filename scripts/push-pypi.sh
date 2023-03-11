#!/bin/bash

set -e

source ~/common/bin/activate

# cleanup
rm -rf dist build *egg*

# build wheel
python setup.py bdist_wheel

if [ "${CI_COMMIT_BRANCH}" == "main" ]; then
    twine upload -r pypi --skip-existing dist/*
fi
