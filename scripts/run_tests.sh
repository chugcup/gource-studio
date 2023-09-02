#!/bin/bash

POSITIONAL_ARGS=()
USE_COVERAGE=0

while [[ $# -gt 0 ]]; do
  case $1 in
    --coverage)
      USE_COVERAGE=1
      shift
      ;;
    *)
      POSITIONAL_ARGS+=("$1") # save positional arg
      shift # past argument
      ;;
  esac
done

source env/bin/activate
if [[ "$(which coverage)" == "" || "$USE_COVERAGE" != "1" ]]; then
    pytest "${POSITIONAL_ARGS[@]}"
else
    coverage run -m pytest "${POSITIONAL_ARGS[@]}" \
        && coverage report
fi
