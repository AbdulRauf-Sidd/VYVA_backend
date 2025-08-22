#!/bin/bash

PORT=8000

echo "Looking for processes on port $PORT..."

# Find the PID(s) using the port
PIDS=$(lsof -ti tcp:$PORT)

if [ -z "$PIDS" ]; then
  echo "No process found using port $PORT."
else
  echo "Killing processes: $PIDS"
  kill -9 $PIDS
  echo "Done."
fi
