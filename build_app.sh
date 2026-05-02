#!/bin/bash
set -e

PYTHON=/opt/homebrew/bin/python3.13

echo "Building HomenetMon.app..."
$PYTHON -m PyInstaller HomenetMon.spec --noconfirm

echo "Fixing code signature..."
xattr -cr dist/HomenetMon.app
codesign -s - --force --all-architectures dist/HomenetMon.app

echo ""
echo "Done. App is at dist/HomenetMon.app"
echo "To install: drag dist/HomenetMon.app to your Applications folder."
