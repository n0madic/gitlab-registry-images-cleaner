#!/bin/sh
set -e

cd /app
source .env/bin/activate
./gricleaner.py "$@"
