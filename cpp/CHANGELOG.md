# Changelog

All notable changes to SC88 Sysex Toolbox (the JUCE app in `cpp/`) are listed here.
Versions follow [Semantic Versioning](https://semver.org): bump the patch number for fixes,
the minor number for new features, and the major number for breaking changes.

The version number lives in one place, the `project(... VERSION x.y.z ...)` line in
`cpp/CMakeLists.txt`. It flows into the app bundle (`CFBundleShortVersionString` /
`CFBundleVersion` in Info.plist on macOS, the version resource on Windows).

## [1.0.0] - 2026-11-02

First official release of the C++/JUCE rewrite of SC88 Flashlight.

- `sc88-core`: framework-independent SC-88 Pro SysEx library, with golden tests against the
  Python app.
- JUCE desktop app with an 88emu-style front panel, resizable window and red LCD value fields.
- Renamed to SC88 Sysex Toolbox; GS/GM reset also resets the editor's values; app icon.
- `build_universal.sh` to build and install a universal Mac app.
- Programs row: per-part program setup with a grouped sound menu.
