#!/bin/sh
# Builds SC88 Sysex Toolbox for macOS as a universal (Apple Silicon + Intel) app.
#
#   ./build_universal.sh            build only
#   ./build_universal.sh install    build, then copy the app to /Applications
#                                   (or ~/Applications if /Applications isn't writable)
#   ./build_universal.sh clean      remove the build folder
set -eu

cd "$(dirname "$0")"
BUILD_DIR=cpp/build-universal
APP_NAME="SC88 Sysex Toolbox.app"
APP="$BUILD_DIR/app/SC88SysexToolbox_artefacts/Release/$APP_NAME"

if [ "$(uname)" != "Darwin" ]; then
    echo "build_universal.sh is for macOS. See cpp/README.md for other platforms." >&2
    exit 1
fi

if ! command -v cmake >/dev/null 2>&1; then
    echo "cmake not found. Install it with 'brew install cmake' or from cmake.org." >&2
    exit 1
fi

case "${1:-}" in
    clean)
        rm -rf "$BUILD_DIR"
        echo "Removed $BUILD_DIR"
        exit 0
        ;;
    ""|install) ;;
    *)
        echo "usage: $0 [install|clean]" >&2
        exit 1
        ;;
esac

cmake -S cpp -B "$BUILD_DIR" \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_OSX_ARCHITECTURES="arm64;x86_64" \
    -DCMAKE_OSX_DEPLOYMENT_TARGET=11.0
cmake --build "$BUILD_DIR" --config Release --parallel
ctest --test-dir "$BUILD_DIR" -C Release --output-on-failure

echo
lipo -info "$APP/Contents/MacOS/SC88 Sysex Toolbox"
echo "Built: $APP"

if [ "${1:-}" = "install" ]; then
    DEST=/Applications
    if [ ! -w "$DEST" ]; then
        DEST="$HOME/Applications"
        mkdir -p "$DEST"
    fi
    rm -rf "$DEST/$APP_NAME"
    ditto "$APP" "$DEST/$APP_NAME"
    echo "Installed: $DEST/$APP_NAME"
fi
