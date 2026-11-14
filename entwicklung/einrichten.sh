#!/bin/bash
# Prüf- und Bauskripte an ihren erwarteten Ort kopieren
set -e
Q="$(cd "$(dirname "$0")" && pwd)/t"
mkdir -p /tmp/claude-0/t
cp -rp "$Q/." /tmp/claude-0/t/
chmod +x /tmp/claude-0/t/fake/chrome /tmp/claude-0/t/lauf/*.sh /tmp/claude-0/t/inst/bauen.sh 2>/dev/null || true
echo "Eingerichtet unter /tmp/claude-0/t"
