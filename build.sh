#!/usr/bin/env bash
# Linux / macOS build script for the C++ DNS Resolver
set -e

SRC="core/dns_resolver.cpp"
OUT="core/dns_resolver"
FLAGS="-std=c++17 -O2 -Wall -Wextra"

echo "[1/2] Checking for g++..."
if ! command -v g++ &> /dev/null; then
    echo "ERROR: g++ not found.  Install with: sudo apt install g++ (Debian/Ubuntu)"
    exit 1
fi

echo "[2/2] Compiling $SRC ..."
g++ $FLAGS "$SRC" -o "$OUT"

echo ""
echo "Build SUCCESS: $OUT"
echo ""
echo "Test it:"
echo "  ./$OUT google.com A"
