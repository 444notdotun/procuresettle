#!/usr/bin/env bash

set -euo pipefail

EXPECTED_NAME="${EXPECTED_GIT_NAME:-A-one-tech}"
EXPECTED_EMAIL_DOMAIN="${EXPECTED_GIT_EMAIL_DOMAIN:-github.com}"

name="$(git config --get user.name 2>/dev/null || true)"
email="$(git config --get user.email 2>/dev/null || true)"

if [[ -z "${name//[[:space:]]/}" ]]; then
    echo "Error: git config user.name is not configured or is empty."
    echo "Set it with: git config user.name '$EXPECTED_NAME'"
    exit 1
fi

if [[ -z "${email//[[:space:]]/}" ]]; then
    echo "Error: git config user.email is not configured or is empty."
    echo "Set it with: git config user.email '$EXPECTED_NAME@users.noreply.$EXPECTED_EMAIL_DOMAIN'"
    exit 1
fi

if [[ ! "$email" =~ ^[^@[:space:]]+@([^@[:space:]]+)$ ]]; then
    echo "Error: git config user.email '$email' is not in a valid email format."
    echo "Set a valid address, for example: git config user.email '$EXPECTED_NAME@users.noreply.$EXPECTED_EMAIL_DOMAIN'"
    exit 1
fi

email_domain="${BASH_REMATCH[1]}"
if [[ "$email_domain" != "$EXPECTED_EMAIL_DOMAIN" && "$email_domain" != *".$EXPECTED_EMAIL_DOMAIN" ]]; then
    echo "Error: git config user.email '$email' does not belong to the expected '$EXPECTED_EMAIL_DOMAIN' domain."
    echo "Use a matching profile address, for example: git config user.email '$EXPECTED_NAME@users.noreply.$EXPECTED_EMAIL_DOMAIN'"
    exit 1
fi

if [[ "$name" != "$EXPECTED_NAME" ]]; then
    echo "Warning: git config user.name '$name' differs from the expected profile name '$EXPECTED_NAME'."
    echo "To use the expected profile: git config user.name '$EXPECTED_NAME'"
fi

echo "Git identity OK: $name <$email>"
