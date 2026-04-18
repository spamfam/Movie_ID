#!/usr/bin/env python3
"""
Movie Folder Renamer
Uses the imdbinfo package to find IMDB IDs for your movie folders
and renames them to include the IMDB ID.

Before running:
    pip install imdbinfo

Usage:
    python rename_movies.py                           # launches GUI
    python rename_movies.py /path/to/movies           # CLI dry run (preview only)
    python rename_movies.py /path/to/movies --rename  # CLI live run
"""

import os
import re
import sys
import json
import time
import argparse
import threading
import tkinter as tk
from tkinter import filedialog, scrolledtext, ttk, messagebox
from datetime import datetime

try:
    from imdbinfo import search_title, TitleType
except ImportError:
    print("ERROR: imdbinfo is not installed.")
    print("Fix it by running:  pip install imdbinfo")
    sys.exit(1)


# ─── Constants ────────────────────────────────────────────────────────────────

UNDO_LOG = "rename_undo_log.json"   # saved alongside the script
MEDIA_EXT = ('.mp4', '.mkv', '.avi', '.srt', '.idx',
             '.sub', '.png', '.jpg', '.jpeg')


# ─── Undo log helpers ─────────────────────────────────────────────────────────

def load_undo_log():
    """Load all saved sessions from the undo log, or return empty list."""
    if not os.path.exists(UNDO_LOG):
        return []
    try:
        with open(UNDO_LOG, "r") as f:
            return json.load(f)
    except Exception:
        return []


def save_undo_log(sessions):
    """Persist all sessions to the undo log."""
    with open(UNDO_LOG, "w") as f:
        json.dump(sessions, f, indent=2)


def record_session(session):
    """Append a completed rename session to the undo log."""
    sessions = load_undo_log()
    sessions.append(session)
    save_undo_log(sessions)


# ─── Core helpers ─────────────────────────────────────────────────────────────

def parse_folder_name(folder_name):
    """
    Extract title and year from a folder named like:  The Dark Knight (2008)
    Returns: ("The Dark Knight", "2008")  or  ("The Dark Knight", None)
    """
    match = re.match(r"^(.+?)\s*\((\d{4})\)\s*$", folder_name)
    if match:
        return match.group(1).strip(), match.group(2)
    return folder_name.strip(), None


def already_processed(folder_name):
    """
    Skip directories that have already been processed or should never be processed:
    - Folders with an IMDb ID e.g. "Movie Title (2008) {imdb-tt0468569}"
    - Folders manually tagged "(No IMDB)" for collections, home movies, or
      anything that will never have an IMDb entry
    """
    return bool(re.search(r'\{imdb-tt\d+\}|\(No IMDB\)', folder_name))


def search_imdb(title):
    """
    Search IMDB using imdbinfo and return top 5 results as a list of dicts
    with keys: title, year, imdb_id, kind — matching the shape the rest of
    the script expects.
    """
    time.sleep(0.5)  # be polite to IMDB servers
    results = search_title(title, title_type=TitleType.Movies)
    return [
        {
            "title":   m.title,
            "year":    str(m.year) if m.year else "",
            "imdb_id": m.imdb_id,
            "kind":    "movie",
        }
        for m in (results.titles or [])[:5]
    ]


def rename_folder_and_files(movies_dir, folder, new_folder_name, log_fn):
    """
    Rename a folder and any media files inside it whose names contain
    the original folder name. Returns a dict describing what changed,
    for use in the undo log. Returns None on failure.
    The caller is responsible for writing summary + expandable file detail
    to the log — this function only returns the data.
    """
    old_folder_path = os.path.join(movies_dir, folder)
    new_folder_path = os.path.join(movies_dir, new_folder_name)

    file_renames = []  # list of {old, new} for files inside
    file_errors  = []

    # ── Rename matching files inside the folder first ──
    try:
        for filename in os.listdir(old_folder_path):
            if not filename.endswith(MEDIA_EXT):
                continue
            if folder not in filename:
                continue
            name, ext = os.path.splitext(filename)
            # Strip any existing IMDB tag from the base name before appending
            clean_name = re.sub(r'\s*\{imdb-tt\d+\}', '', name)
            imdb_tag   = re.search(r'\{imdb-tt\d+\}', new_folder_name)
            tag_str    = f" {imdb_tag.group()}" if imdb_tag else ""
            new_filename = f"{clean_name}{tag_str}{ext}"

            old_file = os.path.join(old_folder_path, filename)
            new_file = os.path.join(old_folder_path, new_filename)
            try:
                os.rename(old_file, new_file)
                file_renames.append({"old": filename, "new": new_filename})
            except OSError as e:
                file_errors.append(f"{filename}: {e}")
    except OSError as e:
        log_fn(f"          ✗ Could not read folder contents: {e}")

    if file_errors:
        for err in file_errors:
            log_fn(f"          ✗ File rename error: {err}")

    # ── Rename the folder itself ──
    try:
        os.rename(old_folder_path, new_folder_path)
    except OSError as e:
        log_fn(f"          ✗ Folder rename failed: {e}")
        return None

    return {
        "old_folder": folder,
        "new_folder": new_folder_name,
        "files":      file_renames
    }


# ─── CLI mode ─────────────────────────────────────────────────────────────────

def process_movies(movies_dir, do_rename=False, log_fn=print,
                   progress_fn=None, stop_flag=None):
    """
    CLI-mode processing. Auto-picks the top IMDB result for each folder.
    """
    try:
        entries = sorted(os.listdir(movies_dir))
    except FileNotFoundError:
        log_fn(f"ERROR: Directory not found: {movies_dir}")
        return

    folders = [e for e in entries
               if os.path.isdir(os.path.join(movies_dir, e))]

    if not folders:
        log_fn("No subdirectories found in that path.")
        return

    total = len(folders)
    log_fn(f"\n{'='*55}")
    log_fn(f"  {'LIVE RUN' if do_rename else 'DRY RUN (preview only)'}")
    log_fn(f"  Directory : {movies_dir}")
    log_fn(f"  Folders   : {total}")
    log_fn(f"{'='*55}\n")

    counts  = {"renamed": 0, "skipped": 0, "failed": 0}
    session = {
        "timestamp":  datetime.now().isoformat(),
        "movies_dir": movies_dir,
        "renames":    []
    }

    for i, folder in enumerate(folders, 1):
        if stop_flag and stop_flag.is_set():
            log_fn("\n⛔ Stopped by user.")
            break
        if progress_fn:
            progress_fn(i, total)
        if already_processed(folder):
            log_fn(f"[SKIP]    {folder}")
            counts["skipped"] += 1
            continue

        title, year = parse_folder_name(folder)
        log_fn(f"[SEARCH]  '{title}' ({year or 'year unknown'}) ...")

        try:
            results = search_imdb(title)
        except Exception as e:
            log_fn(f"          ✗ Search error: {e}")
            counts["failed"] += 1
            continue

        if not results:
            log_fn(f"          ✗ Not found on IMDB")
            counts["failed"] += 1
            continue

        movie      = results[0]
        imdb_id    = movie["imdb_id"]
        new_name   = f"{folder} {{imdb-tt{imdb_id}}}"

        log_fn(f"          → tt{imdb_id}  "
               f"({movie['title']}, {movie['year']})")
        log_fn(f"          {folder}  →  {new_name}")

        if do_rename:
            entry = rename_folder_and_files(movies_dir, folder, new_name, log_fn)
            if entry:
                session["renames"].append(entry)
                counts["renamed"] += 1
                n_files = len(entry["files"])
                if n_files:
                    log_fn(f"          📁 Folder renamed  |  📄 {n_files} file(s) renamed inside")
                    for fr in entry["files"]:
                        log_fn(f"             • {fr['old']}  →  {fr['new']}")
                else:
                    log_fn(f"          📁 Folder renamed  |  no matching files inside")
            else:
                counts["failed"] += 1
        else:
            counts["renamed"] += 1

        log_fn("")

    if do_rename and session["renames"]:
        record_session(session)
        log_fn(f"  💾 Undo log saved to {UNDO_LOG}")

    log_fn(f"\n{'='*55}")
    log_fn(f"  SUMMARY")
    log_fn(f"{'='*55}")
    if do_rename:
        log_fn(f"  ✓ Renamed  : {counts['renamed']}")
    else:
        log_fn(f"  ✓ Would rename : {counts['renamed']}  (run with --rename to apply)")
    log_fn(f"  ⏭  Skipped  : {counts['skipped']}")
    log_fn(f"  ✗ Failed   : {counts['failed']}")
    log_fn("")


# ─── Undo Window ──────────────────────────────────────────────────────────────

class UndoWindow(tk.Toplevel):
    """
    Shows all saved rename sessions and lets the user undo them
    — either the entire session at once, or individual renames one at a time.
    """

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Undo Renames")
        self.grab_set()
        self.minsize(700, 500)
        self.sessions = load_undo_log()
        self._build_ui()

    def _build_ui(self):
        pad = dict(padx=10, pady=5)

        tk.Label(self, text="Saved rename sessions:",
                 font=("Helvetica", 11, "bold")).pack(anchor="w", **pad)

        if not self.sessions:
            tk.Label(self, text="No undo history found.",
                     fg="#888").pack(**pad)
            tk.Button(self, text="Close", command=self.destroy).pack()
            return

        # ── Session list ──
        session_frame = tk.Frame(self)
        session_frame.pack(fill="x", **pad)

        tk.Label(session_frame, text="Session:").pack(side="left")
        self.session_var = tk.IntVar(value=len(self.sessions) - 1)
        self.session_menu = ttk.Combobox(
            session_frame,
            state="readonly",
            width=55,
            values=[
                f"{i+1}:  {s['timestamp'][:19]}  —  "
                f"{len(s['renames'])} renames  —  {s['movies_dir']}"
                for i, s in enumerate(self.sessions)
            ]
        )
        self.session_menu.current(len(self.sessions) - 1)
        self.session_menu.pack(side="left", padx=5)
        self.session_menu.bind("<<ComboboxSelected>>", self._load_session)

        # ── Rename list ──
        tk.Label(self, text="Renames in this session (select to undo individually):",
                 anchor="w").pack(fill="x", **pad)

        list_frame = tk.Frame(self)
        list_frame.pack(fill="both", expand=True, padx=10)

        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side="right", fill="y")

        self.rename_list = tk.Listbox(
            list_frame, selectmode="extended",
            yscrollcommand=scrollbar.set, font=("Courier", 9), height=14
        )
        self.rename_list.pack(fill="both", expand=True)
        scrollbar.config(command=self.rename_list.yview)

        # ── Buttons ──
        btn_frame = tk.Frame(self)
        btn_frame.pack(fill="x", **pad)

        tk.Button(
            btn_frame, text="↩  Undo Selected",
            command=self._undo_selected,
            bg="#FF9800", fg="white", width=18
        ).pack(side="left", padx=(0, 5))

        tk.Button(
            btn_frame, text="↩↩  Undo Entire Session",
            command=self._undo_session,
            bg="#f44336", fg="white", width=22
        ).pack(side="left")

        tk.Button(
            btn_frame, text="Close",
            command=self.destroy, width=10
        ).pack(side="right")

        # ── Log ──
        tk.Label(self, text="Undo log:", anchor="w").pack(fill="x", padx=10)
        self.log = scrolledtext.ScrolledText(
            self, height=6, font=("Courier", 9), state="disabled"
        )
        self.log.pack(fill="x", padx=10, pady=5)

        self._load_session()

    def _load_session(self, event=None):
        """
        Populate the rename list for the currently selected session.
        Each folder entry is followed by indented file detail lines.
        We track which listbox rows map to which rename index so that
        selecting a file-detail row still undoes its parent folder.
        """
        idx = self.session_menu.current()
        self.rename_list.delete(0, "end")
        # Maps listbox row index → rename index in session["renames"]
        self._row_to_rename_idx = {}
        row = 0
        for ri, r in enumerate(self.sessions[idx]["renames"]):
            n_files = len(r.get("files", []))
            summary = (f"📁  {r['new_folder']}  →  {r['old_folder']}"
                       f"  [{n_files} file(s)]")
            self.rename_list.insert("end", summary)
            self.rename_list.itemconfig(row, fg="#000000")
            self._row_to_rename_idx[row] = ri
            row += 1
            for fr in r.get("files", []):
                detail = f"    📄  {fr['new']}  →  {fr['old']}"
                self.rename_list.insert("end", detail)
                self.rename_list.itemconfig(row, fg="#555555")
                self._row_to_rename_idx[row] = ri  # same parent rename
                row += 1

    def _log(self, msg):
        self.log.config(state="normal")
        self.log.insert("end", msg + "\n")
        self.log.see("end")
        self.log.config(state="disabled")

    def _do_undo(self, session_idx, rename_indices):
        """
        Reverse the specified renames within a session.
        rename_indices: list of int indices into session["renames"]
        """
        session    = self.sessions[session_idx]
        movies_dir = session["movies_dir"]
        undone     = []

        for ri in rename_indices:
            entry      = session["renames"][ri]
            old_folder = entry["old_folder"]
            new_folder = entry["new_folder"]
            files      = entry.get("files", [])

            new_path = os.path.join(movies_dir, new_folder)
            old_path = os.path.join(movies_dir, old_folder)

            if not os.path.exists(new_path):
                self._log(f"✗ Not found (already undone?): {new_folder}")
                continue

            # ── Restore files inside the folder first ──
            restored_files = []
            for frename in files:
                old_file = os.path.join(new_path, frename["old"])
                new_file = os.path.join(new_path, frename["new"])
                if os.path.exists(new_file):
                    try:
                        os.rename(new_file, old_file)
                        restored_files.append(frename)
                    except OSError as e:
                        self._log(f"  ✗ File restore failed: {frename['new']}: {e}")

            # ── Restore the folder ──
            try:
                os.rename(new_path, old_path)
                n = len(restored_files)
                self._log(f"✓ Restored: {new_folder}  →  {old_folder}  [{n} file(s)]")
                for fr in restored_files:
                    self._log(f"    📄 {fr['new']}  →  {fr['old']}")
                undone.append(ri)
            except OSError as e:
                self._log(f"✗ Folder restore failed: {new_folder}: {e}")

        # Remove undone entries from the session
        self.sessions[session_idx]["renames"] = [
            r for i, r in enumerate(session["renames"])
            if i not in undone
        ]

        # Remove the session entirely if all renames are undone
        if not self.sessions[session_idx]["renames"]:
            self.sessions.pop(session_idx)
            self._log(f"\n🗑  Session fully undone and removed from log.")

        save_undo_log(self.sessions)
        self._refresh_after_undo()

    def _undo_selected(self):
        session_idx  = self.session_menu.current()
        selected     = self.rename_list.curselection()
        if not selected:
            messagebox.showinfo("Nothing selected",
                                "Select one or more renames from the list first.")
            return
        # Resolve selected rows → unique rename indices (file rows map to parent)
        rename_indices = sorted(set(
            self._row_to_rename_idx[row] for row in selected
            if row in self._row_to_rename_idx
        ))
        if not messagebox.askyesno(
            "Confirm undo",
            f"Restore {len(rename_indices)} folder(s) and their files?"
        ):
            return
        self._do_undo(session_idx, rename_indices)

    def _undo_session(self):
        session_idx = self.session_menu.current()
        session     = self.sessions[session_idx]
        n           = len(session["renames"])
        if not messagebox.askyesno(
            "Confirm undo",
            f"Restore all {n} renames from this session?"
        ):
            return
        self._do_undo(session_idx, list(range(n)))

    def _refresh_after_undo(self):
        """Reload the session dropdown and list after an undo."""
        if not self.sessions:
            self.destroy()
            messagebox.showinfo("Undo complete",
                                "All sessions undone. Undo history cleared.")
            return

        current = min(self.session_menu.current(), len(self.sessions) - 1)
        self.session_menu.config(values=[
            f"{i+1}:  {s['timestamp'][:19]}  —  "
            f"{len(s['renames'])} renames  —  {s['movies_dir']}"
            for i, s in enumerate(self.sessions)
        ])
        self.session_menu.current(current)
        self._load_session()


# ─── Review Queue Window ──────────────────────────────────────────────────────

class ReviewQueue(tk.Toplevel):
    """
    Modal window shown after the search phase completes.
    For each folder shows top 5 IMDB candidates side-by-side with the folder
    name. User can pick a candidate, skip, or type a custom search term.
    """

    def __init__(self, parent, queue, movies_dir, do_rename):
        super().__init__(parent)
        self.title("Review Matches")
        self.grab_set()
        self.resizable(True, True)
        self.minsize(720, 600)

        self.queue      = queue
        self.movies_dir = movies_dir
        self.do_rename  = do_rename
        self.index      = 0
        self.decisions  = []   # list of (folder, movie_or_None)

        self._build_ui()
        self._load_item(0)

    def _build_ui(self):
        pad = dict(padx=12, pady=5)

        # ── Header ──
        self.header = tk.Label(self, text="",
                               font=("Helvetica", 12, "bold"))
        self.header.pack(fill="x", **pad)

        # ── Side-by-side comparison ──
        compare = tk.Frame(self, relief="groove", bd=1)
        compare.pack(fill="x", padx=12, pady=4)
        compare.columnconfigure(0, weight=1)
        compare.columnconfigure(1, weight=1)

        tk.Label(compare, text="Your folder name",
                 font=("Helvetica", 9, "bold"), fg="#555").grid(
            row=0, column=0, sticky="w", padx=8, pady=(6, 0))
        tk.Label(compare, text="Selected IMDB candidate",
                 font=("Helvetica", 9, "bold"), fg="#555").grid(
            row=0, column=1, sticky="w", padx=8, pady=(6, 0))

        self.folder_label = tk.Label(compare, text="", anchor="w",
                                     wraplength=300, justify="left")
        self.folder_label.grid(row=1, column=0, sticky="w",
                               padx=8, pady=(0, 8))

        self.candidate_label = tk.Label(compare, text="", anchor="w",
                                        wraplength=300, justify="left",
                                        fg="#1a6eb5")
        self.candidate_label.grid(row=1, column=1, sticky="w",
                                  padx=8, pady=(0, 8))

        # ── Radio buttons ──
        tk.Label(self, text="Choose a match:",
                 anchor="w").pack(fill="x", padx=12, pady=(6, 0))

        radio_outer = tk.Frame(self)
        radio_outer.pack(fill="x", padx=12)

        self.choice_var = tk.IntVar(value=0)
        self.radio_btns = []
        for i in range(5):
            rb = tk.Radiobutton(
                radio_outer, text="", variable=self.choice_var,
                value=i, anchor="w", justify="left",
                command=self._on_radio
            )
            rb.pack(fill="x", pady=1)
            self.radio_btns.append(rb)

        tk.Radiobutton(
            radio_outer,
            text="⏭  Skip this folder (don't rename)",
            variable=self.choice_var, value=-1,
            anchor="w", command=self._on_radio
        ).pack(fill="x", pady=(6, 0))

        # ── Custom search ──
        search_frame = tk.LabelFrame(self, text="Not finding it? Search manually:")
        search_frame.pack(fill="x", padx=12, pady=8)

        self.custom_var = tk.StringVar()
        custom_entry = tk.Entry(search_frame, textvariable=self.custom_var,
                                width=40)
        custom_entry.pack(side="left", padx=8, pady=6)
        custom_entry.bind("<Return>", lambda e: self._custom_search())

        tk.Button(search_frame, text="🔍 Search",
                  command=self._custom_search).pack(side="left", padx=4)

        self.search_status = tk.Label(search_frame, text="", fg="#888")
        self.search_status.pack(side="left", padx=8)

        # ── Navigation ──
        nav = tk.Frame(self)
        nav.pack(fill="x", padx=12, pady=10)

        self.confirm_btn = tk.Button(
            nav, text="Confirm & Next →", command=self._confirm,
            bg="#4CAF50", fg="white", width=18
        )
        self.confirm_btn.pack(side="right")

        self.progress_lbl = tk.Label(nav, text="")
        self.progress_lbl.pack(side="left")

    # ── Data loading ──

    def _load_item(self, idx):
        """Populate the UI for queue item at idx."""
        item    = self.queue[idx]
        folder  = item["folder"]
        results = item["results"]

        self.header.config(text=f"Review {idx + 1} of {len(self.queue)}")
        self.progress_lbl.config(text=f"{idx + 1} / {len(self.queue)}")
        self.folder_label.config(text=folder)
        self.custom_var.set("")
        self.search_status.config(text="")

        # Default to first candidate if available, else skip
        self.choice_var.set(0 if results else -1)
        self._populate_radios(results)
        self._on_radio()

    def _populate_radios(self, results):
        """Fill radio buttons with the given result list."""
        for i, rb in enumerate(self.radio_btns):
            if i < len(results):
                m = results[i]
                rb.config(
                    text=(f"tt{m['imdb_id']}  —  {m['title']}  "
                          f"({m['year']})  [{m['kind']}]"),
                    state="normal"
                )
            else:
                rb.config(text="—", state="disabled")

    # ── Interactions ──

    def _on_radio(self):
        """Update the side-by-side candidate preview on selection change."""
        results = self.queue[self.index]["results"]
        choice  = self.choice_var.get()
        if choice == -1 or choice >= len(results):
            self.candidate_label.config(text="(will be skipped)")
        else:
            m = results[choice]
            self.candidate_label.config(
                text=(f"{m['title']}  ({m['year']})\n"
                      f"tt{m['imdb_id']}  [{m['kind']}]")
            )

    def _custom_search(self):
        """Run a fresh IMDB search with the user-supplied term."""
        term = self.custom_var.get().strip()
        if not term:
            return

        self.search_status.config(text="Searching...", fg="#888")
        self.confirm_btn.config(state="disabled")
        self.update_idletasks()

        def do_search():
            try:
                results = search_imdb(term)
                # Replace the current item's results with the new ones
                self.queue[self.index]["results"] = results
                self.after(0, lambda: self._on_search_done(results))
            except Exception as e:
                self.after(0, lambda: self.search_status.config(
                    text=f"Error: {e}", fg="red"))
                self.after(0, lambda: self.confirm_btn.config(state="normal"))

        threading.Thread(target=do_search, daemon=True).start()

    def _on_search_done(self, results):
        """Called on main thread after a custom search completes."""
        if results:
            self.search_status.config(
                text=f"Found {len(results)} result(s)", fg="green")
            self.choice_var.set(0)
        else:
            self.search_status.config(text="No results found", fg="red")
            self.choice_var.set(-1)

        self._populate_radios(results)
        self._on_radio()
        self.confirm_btn.config(state="normal")

    def _confirm(self):
        """Record decision for the current item and advance."""
        item    = self.queue[self.index]
        folder  = item["folder"]
        results = item["results"]
        choice  = self.choice_var.get()

        if choice == -1 or not results:
            self.decisions.append((folder, None))
        else:
            self.decisions.append((folder, results[choice]))

        self.index += 1
        if self.index < len(self.queue):
            self._load_item(self.index)
        else:
            self._apply_decisions()
            self.destroy()

    # ── Apply decisions ──

    def _apply_decisions(self):
        """Rename (or preview) folders based on confirmed decisions."""
        win = tk.Toplevel(self.master)
        win.title("Rename Results")
        win.minsize(640, 420)

        log = scrolledtext.ScrolledText(win, font=("Courier", 10))
        log.pack(fill="both", expand=True, padx=10, pady=10)

        def write(msg):
            log.insert("end", msg + "\n")
            log.see("end")
            log.update_idletasks()

        write(f"{'='*55}")
        write(f"  {'LIVE RUN' if self.do_rename else 'DRY RUN (preview only)'}")
        write(f"  Decisions reviewed : {len(self.decisions)}")
        write(f"{'='*55}\n")

        renamed  = 0
        skipped  = 0
        failed   = 0
        session  = {
            "timestamp":  datetime.now().isoformat(),
            "movies_dir": self.movies_dir,
            "renames":    []
        }

        for folder, movie in self.decisions:
            if movie is None:
                write(f"[SKIP]    {folder}")
                skipped += 1
                continue

            imdb_id  = movie["imdb_id"]
            new_name = f"{folder} {{imdb-tt{imdb_id}}}"
            write(f"[RENAME]  {folder}")
            write(f"       →  {new_name}")

            if self.do_rename:
                entry = rename_folder_and_files(
                    self.movies_dir, folder, new_name, write)
                if entry:
                    session["renames"].append(entry)
                    renamed += 1
                    n_files = len(entry["files"])
                    if n_files:
                        write(f"          📁 Folder renamed  |  "
                              f"📄 {n_files} file(s) renamed inside")
                        for fr in entry["files"]:
                            write(f"             • {fr['old']}  →  {fr['new']}")
                    else:
                        write(f"          📁 Folder renamed  |  no matching files inside")
                else:
                    failed += 1
            else:
                write(f"          (dry run — not renamed)")
                renamed += 1

            write("")

        if self.do_rename and session["renames"]:
            record_session(session)
            write(f"💾 Undo log saved to {UNDO_LOG}")

        write(f"\n{'='*55}")
        write(f"  SUMMARY")
        write(f"{'='*55}")
        if self.do_rename:
            write(f"  ✓ Renamed  : {renamed}")
        else:
            write(f"  ✓ Would rename : {renamed}  (run without dry run to apply)")
        write(f"  ⏭  Skipped  : {skipped}")
        write(f"  ✗ Failed   : {failed}")

        tk.Button(win, text="Close", command=win.destroy,
                  bg="#555", fg="white").pack(pady=8)


# ─── Main GUI Window ──────────────────────────────────────────────────────────

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Movie Folder Renamer")
        self.resizable(True, True)
        self.minsize(660, 540)
        self._stop_flag = threading.Event()
        self._build_ui()

    def _build_ui(self):
        pad = dict(padx=10, pady=5)

        # ── Folder picker ──
        folder_frame = tk.Frame(self)
        folder_frame.pack(fill="x", **pad)
        tk.Label(folder_frame, text="Movies folder:").pack(side="left")
        self.folder_var = tk.StringVar()
        tk.Entry(folder_frame, textvariable=self.folder_var,
                 width=50).pack(side="left", padx=5, expand=True, fill="x")
        tk.Button(folder_frame, text="Browse…",
                  command=self._browse).pack(side="left")

        # ── Dry run toggle ──
        options_frame = tk.Frame(self)
        options_frame.pack(fill="x", **pad)
        self.dry_run_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            options_frame,
            text="Dry run  (preview only — no files will be renamed)",
            variable=self.dry_run_var
        ).pack(side="left")

        # ── Buttons row ──
        btn_frame = tk.Frame(self)
        btn_frame.pack(fill="x", **pad)

        self.start_btn = tk.Button(
            btn_frame, text="▶  Start", command=self._start,
            width=12, bg="#4CAF50", fg="white")
        self.start_btn.pack(side="left", padx=(0, 5))

        self.stop_btn = tk.Button(
            btn_frame, text="⛔  Stop", command=self._stop,
            width=12, bg="#f44336", fg="white", state="disabled")
        self.stop_btn.pack(side="left", padx=(0, 15))

        tk.Button(
            btn_frame, text="↩  Undo Renames", command=self._open_undo,
            width=16, bg="#FF9800", fg="white"
        ).pack(side="left")

        # ── Progress bar ──
        self.progress = ttk.Progressbar(self, mode="determinate")
        self.progress.pack(fill="x", padx=10, pady=(5, 0))
        self.progress_label = tk.Label(self, text="", anchor="w")
        self.progress_label.pack(fill="x", padx=10)

        # ── Live log ──
        tk.Label(self, text="Search log:", anchor="w").pack(fill="x", padx=10)
        self.log_box = scrolledtext.ScrolledText(
            self, state="disabled", height=20, font=("Courier", 10)
        )
        self.log_box.pack(fill="both", expand=True, padx=10, pady=5)

    def _browse(self):
        folder = filedialog.askdirectory(title="Select your movies folder")
        if folder:
            self.folder_var.set(folder)

    def _log(self, message):
        """Thread-safe log writer."""
        def _write():
            self.log_box.config(state="normal")
            self.log_box.insert("end", message + "\n")
            self.log_box.see("end")
            self.log_box.config(state="disabled")
        self.after(0, _write)

    def _update_progress(self, current, total):
        """Thread-safe progress update."""
        def _update():
            self.progress["maximum"] = total
            self.progress["value"]   = current
            self.progress_label.config(
                text=f"{current} / {total} folders searched")
        self.after(0, _update)

    def _start(self):
        movies_dir = self.folder_var.get().strip()
        if not movies_dir:
            self._log("⚠️  Please select a movies folder first.")
            return

        self.log_box.config(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.config(state="disabled")
        self.progress["value"] = 0
        self.progress_label.config(text="")
        self._stop_flag.clear()
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")

        do_rename = not self.dry_run_var.get()
        threading.Thread(
            target=self._search_phase,
            args=(movies_dir, do_rename),
            daemon=True
        ).start()

    def _search_phase(self, movies_dir, do_rename):
        """
        Background thread: searches IMDB for all folders and builds the review
        queue. No renaming happens here — deferred entirely to ReviewQueue.
        """
        try:
            entries = sorted(os.listdir(movies_dir))
        except FileNotFoundError:
            self._log(f"ERROR: Directory not found: {movies_dir}")
            self._reset_buttons()
            return

        folders = [e for e in entries
                   if os.path.isdir(os.path.join(movies_dir, e))]

        if not folders:
            self._log("No subdirectories found.")
            self._reset_buttons()
            return

        total   = len(folders)
        queue   = []
        skipped = 0

        self._log(f"Found {total} folders. Searching IMDB...\n")

        for i, folder in enumerate(folders, 1):
            if self._stop_flag.is_set():
                self._log("\n⛔ Stopped by user.")
                self._reset_buttons()
                return

            self._update_progress(i, total)

            if already_processed(folder):
                self._log(f"[SKIP]   {folder}")
                skipped += 1
                continue

            title, year = parse_folder_name(folder)
            self._log(f"[SEARCH] '{title}' ({year or 'year unknown'}) ...")

            try:
                results = search_imdb(title)
            except Exception as e:
                self._log(f"         ✗ Error: {e}")
                results = []

            if not results:
                self._log(f"         ✗ No results — use custom search in review")
            else:
                best = results[0]
                self._log(
                    f"         → top match: {best['title']} "
                    f"({best['year']})  tt{best['imdb_id']}"
                )

            queue.append({"folder": folder, "results": results})

        self._log(
            f"\n✅ Search complete. "
            f"{len(queue)} to review, {skipped} skipped.\n"
            f"Opening review window..."
        )
        self.after(0, lambda: self._open_review(queue, movies_dir, do_rename))
        self.after(0, self._reset_buttons)

    def _open_review(self, queue, movies_dir, do_rename):
        if not queue:
            self._log("Nothing to review!")
            return
        ReviewQueue(self, queue, movies_dir, do_rename)

    def _open_undo(self):
        UndoWindow(self)

    def _reset_buttons(self):
        self.after(0, lambda: self.start_btn.config(state="normal"))
        self.after(0, lambda: self.stop_btn.config(state="disabled"))

    def _stop(self):
        self._stop_flag.set()
        self.stop_btn.config(state="disabled")


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) > 1:
        parser = argparse.ArgumentParser(
            description="Rename movie folders to include their IMDB ID."
        )
        parser.add_argument("directory", help="Path to your movies folder")
        parser.add_argument(
            "--rename", action="store_true",
            help="Actually rename folders (default is dry-run/preview only)"
        )
        args = parser.parse_args()
        process_movies(os.path.abspath(args.directory), do_rename=args.rename)
    else:
        app = App()
        app.mainloop()
