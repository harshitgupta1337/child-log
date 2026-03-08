#!/bin/bash

set -e

echo "Running ngrok daemon"
./ngrok-daemon.sh

echo "ngrok status: $?"

echo "Launching the app"
./app-runner.sh
