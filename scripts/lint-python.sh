#!/usr/bin/env bash

set -euo pipefail

ruff check scripts/
ruff format --check scripts/
