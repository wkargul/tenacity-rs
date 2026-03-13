#!/usr/bin/env bash
# Build and install tenacity-rs in development mode.
# Sets PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1 so the build works with Python 3.13.
export PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1
exec maturin develop "$@"
