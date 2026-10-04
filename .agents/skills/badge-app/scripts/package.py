#!/usr/bin/env python3
"""Package one Badgeware app for badge.select; does not run or deploy it."""

import argparse
from pathlib import Path
import re
import sys
import zipfile

MAX_FILES, MAX_TEXT, MAX_TOTAL = 128, 256 * 1024, 1024 * 1024
SKIP = {"__MACOSX", ".DS_Store", ".git", ".gitignore", ".gitattributes", ".gitkeep", "__pycache__"}
RESERVED_PATHS = {"__proto__", "prototype", "constructor"}
TEXT = re.compile(r"\.(?:py|json|txt|md|csv|svg|toml|ini|cfg|ya?ml|html?|css|js|xml|rst)$", re.I)


def fail(message):
    raise ValueError(message)


def package(name):
    workspace = Path(__file__).resolve().parents[1]
    if not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", name) or name in RESERVED_PATHS:
        fail("Use one app folder name: 1–64 lowercase letters, numbers, _ or -, starting with a letter.")
    if name == "dist":
        fail("Choose an app folder other than dist; dist is the package output folder.")
    app = workspace / name
    if app.is_symlink() or not app.is_dir():
        fail(f"{name}: choose a real app directory beside README.md, not a symlink.")
    files = []
    total = 0

    def collect(folder):
        nonlocal total
        for path in sorted(folder.iterdir()):
            relative = path.relative_to(app).as_posix()
            if path.is_symlink():
                fail(f"{relative}: symlinks are not packaged. Copy the intended file into the app instead.")
            if path.name in SKIP or path.name.startswith("._") or (path.is_file() and re.search(r"\.py[co]$", path.name, re.I)):
                continue
            # Match the browser importer, including the app wrapper's length.
            archive_path = f"{name}/{relative}"
            if len(archive_path) > 160 or any(
                not re.fullmatch(r"[a-zA-Z0-9_][a-zA-Z0-9_.-]*", part) or part.lower() in RESERVED_PATHS
                for part in path.relative_to(app).parts
            ):
                fail(f"{relative}: use a shorter relative path with letters, numbers, _, - and dots; no hidden names.")
            if path.is_dir():
                collect(path)
                continue
            if not path.is_file():
                fail(f"{relative}: only regular files and folders are supported.")
            if len(files) >= MAX_FILES:
                fail("An app may contain at most 128 files and assets.")
            with path.open("rb") as source:
                data = source.read(MAX_TOTAL + 1)
            total += len(data)
            if total > MAX_TOTAL:
                fail(f"{relative}: app files and assets must total 1 MiB or less.")
            if TEXT.search(relative) or path.name.upper() in {"README", "LICENSE", "COPYING"}:
                try:
                    data.decode("utf-8")
                except UnicodeDecodeError:
                    if path.suffix.lower() == ".py":
                        fail(f"{relative}: save Python source as UTF-8.")
                    # Like the importer, non-Python files that aren't UTF-8
                    # remain binary assets, even if their extension suggests text.
                else:
                    if len(data) > MAX_TEXT:
                        fail(f"{relative}: each UTF-8 text file must be 256 KiB or smaller.")
            files.append((archive_path, data))

    collect(app)
    if not any(path == f"{name}/__init__.py" for path, _ in files):
        fail(f"{name}: add an __init__.py entry file at the app folder's root.")
    output_dir = workspace / "dist"
    output = output_dir / f"{name}.zip"
    if output_dir.is_symlink() or output.is_symlink():
        fail("The dist directory and output ZIP must not be symlinks.")
    output_dir.mkdir(exist_ok=True)
    # Finish preflight before replacing a previous package. Only app bytes are
    # included; workspace instructions and agent skills stay outside the ZIP.
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path, data in files:
            archive.writestr(path, data)
    print(f"Created {output}: {len(files)} files, {total} uncompressed bytes. Import it in Make, then choose Run.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("app_folder", nargs="?", default="my_badge_app", help="App folder beside README.md (default: my_badge_app)")
    try:
        package(parser.parse_args().app_folder)
    except (OSError, ValueError) as error:
        print(f"Cannot package app: {error}", file=sys.stderr)
        sys.exit(1)
