#!/usr/bin/env bash
#
# Allow the dev server through the macOS application firewall so phones on the
# same Wi-Fi can reach `python manage.py runserver 0.0.0.0:8000`.
#
# Homebrew's Python is unsigned, so the firewall silently drops inbound LAN
# connections to it: the connection is accepted and then killed on the first
# read, which Safari reports as "the network connection was lost". The rule is
# keyed to the real binary path, so `brew upgrade python` invalidates it and
# this script has to run again.
#
# Usage: sudo tools/allow_lan_dev_server.sh
set -euo pipefail

FIREWALL=/usr/libexec/ApplicationFirewall/socketfilterfw
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PYTHON="$REPO_ROOT/venv/bin/python"

if [ "$(uname -s)" != "Darwin" ]; then
  echo "This script only applies to macOS." >&2
  exit 1
fi

if [ "$(id -u)" -ne 0 ]; then
  echo "Run with sudo: sudo tools/allow_lan_dev_server.sh" >&2
  exit 1
fi

if [ ! -x "$VENV_PYTHON" ]; then
  echo "No virtualenv Python at $VENV_PYTHON" >&2
  exit 1
fi

# realpath matters: sys.base_prefix reports the /usr/local/opt symlink, and a
# rule added for the symlink never matches the running process.
BUNDLE="$("$VENV_PYTHON" -c \
  'import os, sys; print(os.path.realpath(sys.base_prefix) + "/Resources/Python.app")')"

if [ ! -d "$BUNDLE" ]; then
  echo "Expected a Python.app bundle at $BUNDLE" >&2
  exit 1
fi

echo "Allowing inbound connections for:"
echo "  $BUNDLE"
"$FIREWALL" --add "$BUNDLE" > /dev/null
"$FIREWALL" --unblockapp "$BUNDLE" > /dev/null
"$FIREWALL" --getappblocked "$BUNDLE"

echo
echo "Restart the dev server so a fresh process picks up the rule:"
echo "  python manage.py runserver 0.0.0.0:8000"
