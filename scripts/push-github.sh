#!/bin/bash

set -ex

if [ "${CI_COMMIT_BRANCH}" == "main" ]; then
  echo "ensuring local clone does not exist"
  test -e gitlab && rm -rfv gitlab
  echo "cloning from gitlab"
  git clone git@gitlab.botthouse.net:botthouse/bf2pico.git gitlab
  cd gitlab
  echo "adding github repo"
  git remote add github git@github.com:tmb28054/bf2pico.git
  echo "pushing to github"
  git push -u github main
fi
