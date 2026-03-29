#!/usr/bin/env bash
# build_mac.sh — Build Sift.app and Sift.dmg for macOS
set -euo pipefail

APP_NAME="Sift"
BUNDLE_ID="com.sift.app"
DIST_DIR="dist"

echo "==> Building ${APP_NAME}.app with PyInstaller…"
pyinstaller sift.spec --noconfirm --clean

echo "==> Verifying bundle…"
ls "${DIST_DIR}/${APP_NAME}.app/Contents/MacOS/"

echo "==> Creating DMG…"
create-dmg \
  --volname "${APP_NAME}" \
  --volicon "assets/icon.png" \
  --window-pos 200 120 \
  --window-size 600 400 \
  --icon-size 100 \
  --icon "${APP_NAME}.app" 175 190 \
  --hide-extension "${APP_NAME}.app" \
  --app-drop-link 425 190 \
  "${DIST_DIR}/${APP_NAME}.dmg" \
  "${DIST_DIR}/"

echo ""
echo "==> Done: ${DIST_DIR}/${APP_NAME}.dmg"
echo ""
echo "Optional notarization:"
echo "  xcrun notarytool submit ${DIST_DIR}/${APP_NAME}.dmg \\"
echo "    --apple-id YOUR_APPLE_ID \\"
echo "    --team-id YOUR_TEAM_ID \\"
echo "    --password YOUR_APP_SPECIFIC_PASSWORD \\"
echo "    --wait"
echo "  xcrun stapler staple ${DIST_DIR}/${APP_NAME}.dmg"
