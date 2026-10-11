#!/usr/bin/env bash
# clone RealtimeGym into external/ at the root of this repo
# usage: ./setup_external.sh (works from any folder)
set -euo pipefail

# find the repo root from this script's location, not the caller's folder
script_directory="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(git -C "$script_directory" rev-parse --show-toplevel)"

external_directory="$repo_root/external"
clone_directory="$external_directory/RealtimeGym"
repo_url="https://github.com/SALT-NLP/RealtimeGym.git"

# -p creates the folder only if it doesn't exist yet
mkdir -p "$external_directory"

# don't clone over an existing copy
if [ -d "$clone_directory/.git" ]; then
    echo "RealtimeGym is already cloned at $clone_directory"
elif [ -e "$clone_directory" ]; then
    echo "Error: $clone_directory exists but isn't a git clone" >&2
    exit 1
else
    git clone "$repo_url" "$clone_directory"
    echo "Cloned RealtimeGym into $clone_directory"
fi
