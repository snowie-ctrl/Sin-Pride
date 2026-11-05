"""copyFromGluttony.py against a scratch repository standing in for Gluttony."""
import subprocess
import sys
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parent / "copyFromGluttony.py"


@pytest.fixture
def gluttony(tmp_path, monkeypatch):
    repo = tmp_path / "Gluttony"
    (repo / "app").mkdir(parents=True)
    (repo / "app" / "Thing.h").write_text(
        "// Copied from Pageturner Pageturner/Thing.h at ad9342e; GLUTTONY_ names and\n"
        "// more of the same sentence.\n// It also differs from Showtime in one way.\n// Real comment.\n#pragma once\n"
        "const char *v = \"GLUTTONY_SECRETS /api/gluttony\";\n",
        encoding="utf-8", newline="\n")
    (repo / "app" / "Plain.qml").write_text("import QtQuick\n// Kept.\nItem {}\n", encoding="utf-8", newline="\n")
    for args in (["init", "-q"], ["add", "-A"], ["-c", "user.email=scratch", "-c", "user.name=t", "commit", "-q", "-m", "x"]):
        subprocess.run(["git", "-C", str(repo), *args], check=True)
    commit = subprocess.run(["git", "-C", str(repo), "rev-parse", "--short=7", "HEAD"], capture_output=True, text=True,
                            check=True).stdout.strip()
    monkeypatch.setenv("PRIDE_GLUTTONY", str(repo))
    monkeypatch.setenv("PRIDE_GLUTTONY_COMMIT", commit)
    return repo, commit


def run(*args, cwd):
    return subprocess.run([sys.executable, str(TOOL), *args], capture_output=True, text=True, cwd=cwd)


def test_theHeaderNamesGluttonyAndTheCommitAndRenamesApply(gluttony, tmp_path):
    _, commit = gluttony
    out = tmp_path / "out" / "Thing.h"
    result = run("app/Thing.h", str(out), "PRIDE_ names", "--sub", "GLUTTONY_", "PRIDE_",
                 "--sub", "/api/gluttony", "/api/pride", cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    text = out.read_text(encoding="utf-8")
    assert text.startswith(f"// Copied from Gluttony app/Thing.h at {commit}; PRIDE_ names.\n// Real comment.\n#pragma once\n")
    assert "PRIDE_SECRETS /api/pride" in text and "Pageturner" not in text


def test_aFileWithoutAProvenanceHeaderKeepsItsComments(gluttony, tmp_path):
    out = tmp_path / "Plain.qml"
    assert run("app/Plain.qml", str(out), "as it is", cwd=tmp_path).returncode == 0
    assert out.read_text(encoding="utf-8").endswith("import QtQuick\n// Kept.\nItem {}\n")


def test_aSubstitutionThatMatchesNothingIsAnError(gluttony, tmp_path):
    out = tmp_path / "Thing.h"
    result = run("app/Thing.h", str(out), "x", "--sub", "NOT_THERE", "Y", cwd=tmp_path)
    assert result.returncode != 0 and "NOT_THERE" in result.stderr
    assert not out.exists()
    assert run("app/Thing.h", str(out), "x", "--maybe", "NOT_THERE", "Y", cwd=tmp_path).returncode == 0
