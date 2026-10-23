# SC-88 Pro EFX data refactor — v2.1

Fixes a page-boundary parsing bug discovered while testing GTR Multi 2.

The PDF text extraction split a few effect definitions across pages. The first v2 parser
mistakenly treated the continuation rows as detached from the active effect. Four effects
were affected:

- 24: 4 Tap Delay
- 49: GTR Multi 2
- 55: Keyboard Multi
- 59: OD1 / OD2

Their continuation parameters have now been restored from the manual.

Parameters whose factory default is not unambiguously represented in extracted text remain
marked `default_from_manual: false`; no unsupported default has been invented.
