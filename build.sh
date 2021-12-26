#!/usr/bin/env bash
set -Eeo pipefail

poetry export --dev --without-hashes -f requirements.txt -o requirements.txt
sudo docker build -t cats-test:latest .
