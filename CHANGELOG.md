# Changelog

All notable changes to Pagecraft are documented here.

## 0.2.0 — 2026-08-20

### Added

- Categories, chronological archives, configurable homepage pagination, and a `new-post` authoring command.
- Draft and future-post controls for preview builds.
- Configurable sitemap and `robots.txt` generation, canonical URLs, Open Graph metadata, article timestamps, and richer RSS metadata.
- `check`, JSON build reports, verbose build reports, `serve`, and debounced watch mode.
- Safe route collision detection, stale generated-file removal, stale asset removal, and a versioned incremental-build manifest.
- A responsive built-in theme with a persisted light/dark preference.
- A complete starter project with navigation and publishing defaults.
- CI coverage for Python 3.9 through 3.12, distribution builds, and expanded v0.2 regression tests.

### Changed

- Reworked the internal content and configuration models while preserving the v0.1 configuration shape where possible.
- Rebuilt the public demo as a small journal that exercises categories, tags, pagination, archives, syntax highlighting, feeds, and discovery files.
- Refined package metadata and project links for the v0.2 release.

### Fixed

- Standalone pages without explicit dates are now published by default instead of being accidentally treated as future content.
- Test isolation no longer allows source mutations to survive after a test run.

## 0.1.0

- Initial release with Markdown rendering, layouts, tags, RSS, syntax highlighting, asset copying, and incremental output.
