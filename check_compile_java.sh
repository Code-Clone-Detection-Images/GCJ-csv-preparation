#!/usr/bin/env bash
TMP_DIR=$(mktemp -d -t ci-XXXXXXXXXX)
javac -d "$TMP_DIR" $@