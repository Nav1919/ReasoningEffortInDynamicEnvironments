#!/usr/bin/env bash

set -euo pipefail

readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly EXTERNAL_DIR="${SCRIPT_DIR}/external"
readonly REALTIME_GYM_DIR="${EXTERNAL_DIR}/RealtimeGym"
readonly REALTIME_GYM_REPO="https://github.com/SALT-NLP/RealtimeGym.git"

# Create the directory used for external environment repositories when needed.
mkdir -p "${EXTERNAL_DIR}"

# Clone RealtimeGym only when it is not already available locally.
if [[ ! -e "${REALTIME_GYM_DIR}" ]]; then
    echo "Cloning RealtimeGym into ${REALTIME_GYM_DIR}..."
    git clone "${REALTIME_GYM_REPO}" "${REALTIME_GYM_DIR}"
elif git -C "${REALTIME_GYM_DIR}" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    actual_remote="$(git -C "${REALTIME_GYM_DIR}" remote get-url origin 2>/dev/null || true)"

    if [[ "${actual_remote}" != "${REALTIME_GYM_REPO}" ]]; then
        echo "Error: ${REALTIME_GYM_DIR} is a Git repository, but its origin is:" >&2
        echo "  ${actual_remote:-<not configured>}" >&2
        echo "Expected:" >&2
        echo "  ${REALTIME_GYM_REPO}" >&2
        exit 1
    fi

    echo "RealtimeGym is already cloned at ${REALTIME_GYM_DIR}."
else
    echo "Error: ${REALTIME_GYM_DIR} exists but is not a Git repository." >&2
    echo "Move or remove it, then run this script again." >&2
    exit 1
fi

echo "External environment setup complete."
