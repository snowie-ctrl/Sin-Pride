"""
Copies one file from Gluttony into Pride at a pinned Gluttony commit (spec §1, "Copied foundations"): Gluttony is only
read, with git show, never changed. The copy starts with a header naming its source, the commit and what changed;
Gluttony's own provenance header (a first comment sentence naming Pageturner, Artemis or Showtime) gives way to it.
--sub replacements must each match at least once, so a copy never silently misses a rename; --maybe ones need not.

    py -3.12 tools/copyFromGluttony.py app/api/Api.h app/api/Api.h "put and del" --maybe GLUTTONY_ PRIDE_

Gluttony is looked for beside this repository (../Gluttony) unless PRIDE_GLUTTONY names it.
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
COMMIT = "c1ed705"
PROVENANCE = ("Copied from", "Pageturner", "Artemis", "Showtime")


def commentMark(path):
    return "#" if path.endswith((".py", ".ps1", ".ini", ".txt")) else "//"


def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("source")
    parser.add_argument("target")
    parser.add_argument("changes")
    parser.add_argument("--sub", nargs=2, action="append", default=[], metavar=("OLD", "NEW"))
    parser.add_argument("--maybe", nargs=2, action="append", default=[], metavar=("OLD", "NEW"))
    args = parser.parse_args(argv)

    gluttony = Path(os.environ.get("PRIDE_GLUTTONY") or REPO.parent / "Gluttony")
    commit = os.environ.get("PRIDE_GLUTTONY_COMMIT") or COMMIT
    shown = subprocess.run(["git", "-C", str(gluttony), "show", f"{commit}:{args.source}"], capture_output=True)
    if shown.returncode != 0:
        sys.exit(f"git show {commit}:{args.source} failed: {shown.stderr.decode('utf-8', 'replace').strip()}")
    text = shown.stdout.decode("utf-8").replace("\r\n", "\n")

    mark = commentMark(args.target)
    lines = text.split("\n")
    # The provenance header runs to the end of its sentence, and on through a next line that is provenance too
    # ("It also differs from Showtime ..."); the comments after it are the file's own and stay.
    dropping = bool(lines) and lines[0].startswith(mark) and any(word in lines[0] for word in PROVENANCE)
    while dropping and lines and lines[0].startswith(mark):
        line = lines.pop(0)
        if line.rstrip().endswith("."):
            dropping = bool(lines) and lines[0].startswith(mark) and any(word in lines[0] for word in PROVENANCE)
    text = "\n".join(lines)

    for old, new in args.sub:
        if old not in text:
            sys.exit(f"--sub {old!r} matches nothing in {args.source}")
        text = text.replace(old, new)
    for old, new in args.maybe:
        text = text.replace(old, new)

    header = f"{mark} Copied from Gluttony {args.source} at {commit}; {args.changes}.\n"
    target = Path(args.target)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes((header + text).encode("utf-8"))
    print(f"{args.source} -> {target}")


if __name__ == "__main__":
    main(sys.argv[1:])
