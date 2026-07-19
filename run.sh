#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
OS_NAME=$(uname -s)
ARCH_NAME=$(uname -m)
export CRACKSTACK_ROOT="$SCRIPT_DIR"

PLATFORM=""
case "$OS_NAME:$ARCH_NAME" in
  Linux:x86_64) PLATFORM="linux-x64" ;;
  Darwin:arm64) PLATFORM="macos-arm64" ;;
  Darwin:x86_64) PLATFORM="macos-x64" ;;
esac

if [ -z "$PLATFORM" ]; then
  echo "Unsupported platform: $OS_NAME $ARCH_NAME" >&2
  echo "Add a matching runtime/python/<platform> bundle for this host." >&2
  exit 1
fi

PYTHON_EXE="$SCRIPT_DIR/runtime/python/$PLATFORM/bin/python"
export PYTHONPATH="$SCRIPT_DIR:$SCRIPT_DIR/runtime/site-packages/$PLATFORM${PYTHONPATH:+:$PYTHONPATH}"
export PATH="$SCRIPT_DIR/runtime/python/$PLATFORM/bin:$PATH"
if [ -x "$PYTHON_EXE" ]; then
  exec "$PYTHON_EXE" -m harness.cli "$@"
fi

echo "Bundled Python was not found at:" >&2
echo "  $PYTHON_EXE" >&2
echo "Falling back to host python3 for development only." >&2
exec python3 -m harness.cli "$@"
