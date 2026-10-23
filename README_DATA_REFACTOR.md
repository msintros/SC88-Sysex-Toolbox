# SC-88 Pro EFX data refactor — first scaffold

This is the first-pass DRY architecture for the SC-88-Pro-Toolkit insertion-effect data.

## Why this changes the old representation

The original `efx.json` mixes two different quantities:

1. a UI ordinal/index into a display list; and
2. the actual byte that Roland expects in the SysEx data field.

Those happen to be identical for simple parameters (0–127, Off/On, etc.), but **not** for
Roland's starred lookup tables. For example, the manual's `*10 EQ Freq` table uses sparse
raw byte codes. 1.6 kHz is not ordinal 9 on the MIDI wire.

The new source therefore uses:

- `default_raw`: actual SysEx byte
- `codec`: how that byte should be displayed
- `address`: actual LSB address (03H–16H)
- `controller`: 1 for `+`, 2 for `#`

The generator can still produce the old 20-slot shape for compatibility, but the GUI should
eventually be updated to understand codecs directly.

## Current coverage

The scaffold contains effects 0–6 as a proof of architecture and a set of common codecs.
The next pass should:

1. transcribe Roland Effect Data Tables *1–*14;
2. update the GUI so it increments through valid raw codes rather than `% 128`;
3. populate effects 7–64 directly from the appendix Effect List;
4. add validation against defaults and legal raw values.

## Important bug found in the original project

The original file represents e.g. Stereo-EQ M1 Freq as a short list with default `9`.
The GUI sends that `9` directly as the SysEx data byte. Roland's table encodes EQ frequency
with sparse/raw codes, so the ordinal index and MIDI byte are not interchangeable.

This refactor fixes that at the data-model level rather than patching individual effects.
