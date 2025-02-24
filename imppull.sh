#!/bin/bash
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
FIRST_PWD=$PWD
cd "$SCRIPT_DIR"
. ./bin/activate
python3 imppull.py "$@" --rel "$FIRST_PWD"