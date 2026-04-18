# Contributing to Movie_ID

Thanks for your interest in contributing! Here's how to get started.

---

## Reporting bugs

Open an [issue](https://github.com/spamfam/Movie_ID/issues) and include:

- Your OS and Python version (`python --version`)
- Your imdbinfo version (`pip show imdbinfo`)
- The exact error message or unexpected behavior
- A sample folder name that triggered the issue (redact personal info if needed)

---

## Suggesting features

Open an issue with the `enhancement` label and describe:

- What you want the tool to do
- Why it would be useful
- Any edge cases to consider

---

## Submitting a pull request

1. Fork the repo and create a branch from `main`
2. Make your changes
3. Test against a real movie folder (dry run first!)
4. Open a pull request with a clear description of what changed and why

---

## Code style

- Follow existing patterns — the code uses clear section comments (`# ── Section ──`)
- Keep GUI and core logic separate — `process_movies()` and `rename_folder_and_files()` should stay usable without tkinter
- All file system operations should use absolute paths — no `os.chdir()`
- New features that touch renaming should update the undo log accordingly
