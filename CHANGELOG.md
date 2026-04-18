# Changelog

All notable changes to Movie_ID are documented here.

---

## [Unreleased]

---

## [0.3.0] — GUI, Undo, and File Renaming

### Added
- Full **tkinter GUI** — launches automatically when run with no arguments
- **Review queue** — all IMDB matches are queued for manual confirmation before any renaming occurs
- **Custom search** — type an alternative title mid-review if the top 5 candidates are wrong
- **Undo system** — restore individual folder renames or entire sessions via the GUI
- **Undo log** (`rename_undo_log.json`) — sessions persist between runs so undo is always available
- CLI mode preserved — passing a directory path skips the GUI entirely

### Changed
- Replaced deprecated **cinemagoer** (`IMDbPY`) library with **imdbinfo** — more reliable, actively maintained, no API key required
- Search results are now filtered to `TitleType.Movies` to reduce false matches from TV episodes and series
- `search_imdb()` no longer requires a client object — imdbinfo uses simple function calls

---

## [0.2.0] — CLI Foundation

### Added
- Recursive directory scan using `os.walk`
- IMDB ID lookup via cinemagoer (now replaced — see v0.3.0)
- Skip logic for folders already containing `{imdb-tt...}` or `(No IMDB)` tags
- Error logging to `error.log`
- Dry run mode via `--rename` flag

### Known issues (resolved in v0.3.0)
- cinemagoer `search_movie()` returned empty results due to IMDB endpoint changes
- No GUI — CLI only
- No undo capability
- `os.chdir()` combined with `os.walk()` caused path resolution issues on some systems
- `except Exception` before `except IMDbDataAccessError` made the specific handler unreachable

---
