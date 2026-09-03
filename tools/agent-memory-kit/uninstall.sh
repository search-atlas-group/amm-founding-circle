#!/usr/bin/env bash
# Wrapper: everything lives in uninstall.py so macOS, Linux and Windows run the same code.
exec python3 "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/uninstall.py" "$@"
