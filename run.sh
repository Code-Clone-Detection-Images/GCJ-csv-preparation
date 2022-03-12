#!/usr/bin/env bash

if [ $# -eq 0 ]; then
    echo "Please supply a csv file to parse: run.sh <gcjXXXX.csv>"
    exit 1
fi


if compgen -G "./gcj/*Round*"; then
   echo "[Prepare] Cleaning up gcj folder"
   rm -rf "./gcj/"
else
   echo "[Prepare] No steps required"
fi

# This script is only used to run the docker-container built by the makefile and mount the pwd
echo "[Script] Using docker: $(docker -v)"
# shellcheck disable=SC2089
printf -v b '/home/preparer/%s ' "$@"
# resplitting deliberate
# shellcheck disable=SC2086
docker run --volume "$(pwd):/home/preparer" gjc-prepare:latest $b
