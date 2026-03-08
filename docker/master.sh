#!/bin/bash

echo "Running ngrok daemon"
./ngrok-daemon.sh

echo "Launching the app"
./app-runner.sh
