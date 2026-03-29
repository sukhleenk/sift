#!/usr/bin/env bash
# build_linux.sh — Build Sift AppImage for Linux
set -euo pipefail

APP_NAME="Sift"
ARCH="x86_64"
DIST_DIR="dist"
APPDIR="${DIST_DIR}/${APP_NAME}.AppDir"

echo "==> Building one-folder bundle with PyInstaller…"
pyinstaller sift.spec --noconfirm --clean

echo "==> Preparing AppDir structure…"
mkdir -p "${APPDIR}/usr/bin"
cp -r "${DIST_DIR}/${APP_NAME}/." "${APPDIR}/usr/bin/"

cat > "${APPDIR}/${APP_NAME}.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=${APP_NAME}
Exec=${APP_NAME}
Icon=${APP_NAME}
Categories=Science;Education;
EOF

cp assets/icon.png "${APPDIR}/${APP_NAME}.png"

cat > "${APPDIR}/AppRun" <<'EOF'
#!/bin/bash
SELF=$(readlink -f "$0")
HERE="${SELF%/*}"
exec "${HERE}/usr/bin/sift" "$@"
EOF
chmod +x "${APPDIR}/AppRun"

echo "==> Building AppImage with appimagetool…"
ARCH=${ARCH} appimagetool "${APPDIR}" "${DIST_DIR}/${APP_NAME}-${ARCH}.AppImage"

echo ""
echo "==> Done: ${DIST_DIR}/${APP_NAME}-${ARCH}.AppImage"
echo "    Mark executable: chmod +x ${DIST_DIR}/${APP_NAME}-${ARCH}.AppImage"
