#!/bin/bash
set -e

MESSAGE="$1"

if [ -z "$MESSAGE" ]; then
  echo "Usage: ./migrate.sh \"migration message\""
  exit 1
fi

alembic revision --autogenerate -m "$MESSAGE"
alembic upgrade head
