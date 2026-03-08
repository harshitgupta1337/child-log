#!/bin/bash

cd /child-log

source .venv/bin/activate

export PYTHONPATH=${PYTHONPATH}:$PWD/py-huckleberry-api/src

uvicorn telegram:app --reload --host 0.0.0.0 --port 8000
