#!/usr/bin/env bash

if compgen -G "./gcj/*Round*"; then
   echo "[Prepare] Cleaning up gcj folder"
   rm -rf "./gcj/"
else
   echo "[Prepare] No steps required"
fi

# This script is only used to run the dockercontainer built by the makefile and mount the pwd
echo "[Script] Using docker: $(docker -v)"
docker run --volume "$(pwd):/home/preparer" gjc-prepare:latest "/home/preparer/$@"
