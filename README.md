# 🎬 Movie_ID

A Python tool that recursively scans a directory of movie folders and uses the [imdbinfo](https://github.com/tveronesi/imdbinfo) package to look up each movie's IMDB ID, renaming folders (and media files inside them) to include the ID in a standard format.

Comes with a full **tkinter GUI** for interactive review and an **undo system** so nothing is ever permanent.

---

## Features

- 🔍 **Automatic IMDB lookup** for every movie folder
- 🖥️ **GUI mode** — launches automatically when run without arguments
- 📋 **Review queue** — confirm, skip, or custom-search every match before any renaming happens
- ↩️ **Full undo** — restore individual renames or entire sessions, including files inside folders
- 🏷️ **Smart skipping** — folders already tagged or marked `(No IMDB)` are never re-processed
- 📄 **File renaming** — media files inside each folder are renamed to match
- 🖥️ **CLI mode** — scriptable with dry-run support for automation
- 💾 **Undo log** — all sessions saved to `rename_undo_log.json` and persist between runs

---

## Folder naming format

The tool expects folders named in the format:

```
Movie Title (Year)
```

After renaming:

```
Movie Title (Year) {imdb-tt0068646}
```

### Special tags

| Tag | Meaning |
|---|---|
| `{imdb-tt0000000}` | Already processed — will be skipped |
| `(No IMDB)` | Manually flagged — collections, home movies, anything that will never have an IMDB entry |

---

## Installation

**1. Clone the repo**
```bash
git clone https://github.com/spamfam/Movie_ID.git
cd Movie_ID
```

**2. Install the dependency**
```bash
pip install imdbinfo
```

> ⚠️ **tkinter** is required for GUI mode. It is included in standard Python installers from [python.org](https://www.python.org/downloads/windows/). When installing, choose **Customize Installation** and ensure **tcl/tk and IDLE** is checked.

---

## Usage

### GUI mode (recommended)
```bash
python rename_movies.py
```
Launches the graphical interface. Browse to your movies folder, toggle dry run on/off, hit Start, then review every match before anything is renamed.

### CLI mode
```bash
# Dry run — preview only, nothing is renamed
python rename_movies.py /path/to/movies

# Live run — actually rename folders and files
python rename_movies.py /path/to/movies --rename
```

---

## GUI walkthrough

**1. Search phase**
The app searches IMDB for every unprocessed folder and logs results live. Nothing is renamed yet.

**2. Review queue**
After searching, a review window opens. For each folder you see:
- Your folder name vs the top IMDB candidate side-by-side
- 5 radio button candidates to choose from
- A skip option
- A custom search box if none of the candidates are right

**3. Rename results**
After reviewing all folders, a results window shows exactly what was renamed — including every media file inside each folder — with a full summary.

**4. Undo**
Click **↩ Undo Renames** on the main window at any time to open the undo manager. You can restore individual folders or entire sessions. Files inside folders are restored too.

---

## File renaming

Media files inside each renamed folder are also renamed if their name contains the original folder name. Supported extensions:

`.mp4` `.mkv` `.avi` `.srt` `.idx` `.sub` `.png` `.jpg` `.jpeg`

Example:
```
The Godfather (1972).mkv  →  The Godfather (1972) {imdb-tt0068646}.mkv
The Godfather (1972).srt  →  The Godfather (1972) {imdb-tt0068646}.srt
```

---

## Requirements

- Python 3.8+
- [imdbinfo](https://pypi.org/project/imdbinfo/) (`pip install imdbinfo`)
- tkinter (included in standard Python installs from python.org)

---

## Notes

- Always run a **dry run first** to preview changes before committing
- The undo log (`rename_undo_log.json`) is saved in the same directory as the script
- The tool only processes **top-level subfolders** — it does not recurse into movie folders themselves
- Rate limiting (0.5s between requests) is built in to avoid hitting IMDB servers too hard

---

## Author

[spamfam](https://github.com/spamfam)
