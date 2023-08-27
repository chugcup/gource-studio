#!/bin/bash

source env/bin/activate
if [ "$(which coverage)" == "" ]; then
    pytest "$@"
else
    coverage run -m pytest "$@" \
        && coverage report
fi
