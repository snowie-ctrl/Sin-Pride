"""
Makes snapshot/ (git-ignored) from the importer's last run, so the stub serves the real catalog: run the importer's
dry run first (importer/main.py), then, from the repository root:

    server/.venv/Scripts/python.exe app/tests/stub/snapshot.py

The exercises and pictures are free-exercise-db's (public domain); they stay out of git only because they are large.
"""
import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]


def build(reports=REPO / "importer" / "reports", cache=REPO / "importer" / "cache", out=HERE / "snapshot"):
    last = json.loads((reports / "last-catalog.json").read_text(encoding="utf-8"))
    exercises = sorted(last["exercises"], key=lambda e: (e["name"].casefold(), e["key"]))
    version = hashlib.sha1("\n".join(f"{e['key']} {e['hash']}" for e in exercises).encode("utf-8")).hexdigest()
    listed = [{"id": n, "source": last["source"], "removed": False, **{k: v for k, v in e.items() if k != "hash"}}
              for n, e in enumerate(exercises, start=1)]
    if out.exists():
        shutil.rmtree(out)
    (out / "pictures").mkdir(parents=True)
    for name, path in last["pictures"].items():
        shutil.copyfile(cache / path, out / "pictures" / name)
    (out / "catalog.json").write_text(json.dumps({"version": version, "exercises": listed}, ensure_ascii=False),
                                      encoding="utf-8")
    return len(listed), len(last["pictures"])


if __name__ == "__main__":
    exercises, pictures = build()
    print(f"snapshot/: {exercises} exercises, {pictures} pictures")
