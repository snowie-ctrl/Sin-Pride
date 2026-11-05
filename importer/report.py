"""
The change report: what publishing would do against what the server holds (GET /api/pride-admin/state), and the
hide guard (spec §8). It is printed on every run, dry or not, and kept in importer/reports/, beside the normalised
catalog that the app's stub can serve (app/tests/stub/snapshot.py).
"""
import json
import time

import config


def stateFor(state, sourceName):
    """{key: row} for one source, from GET /state's answer; {} with no server to ask."""
    return {row["key"]: row for row in (state or {}).get("exercises", []) if row.get("source") == sourceName}


def changeReport(payloads, held):
    sent = {p["key"]: p for p in payloads}
    added = sorted(k for k in sent if k not in held)
    changed = sorted(k for k in sent if k in held and (held[k]["hash"] != sent[k]["hash"] or held[k]["removed"]))
    hidden = sorted(k for k, row in held.items() if k not in sent and not row["removed"])
    visible = sum(1 for row in held.values() if not row["removed"])
    names = {k: p["name"] for k, p in sent.items()}
    names.update({k: row.get("name") or k for k, row in held.items() if k not in sent})
    return {"added": added, "changed": changed, "hidden": hidden,
            "unchanged": len(sent) - len(added) - len(changed), "visible": visible, "names": names}


def guardProblem(report, guard):
    hidden, visible = len(report["hidden"]), report["visible"]
    if visible and hidden > guard * visible:
        return (f"publishing would hide {hidden} of {visible} exercises (more than {round(guard * 100)}%); "
                "nothing was published")
    return None


def render(report, limit=40):
    lines = [f"{report['source']} at {report['commit'][:12]}: {report['exercises']} exercises, "
             f"{report['pictures']} pictures"]
    for label, key in (("Added", "added"), ("Changed", "changed"), ("Hidden", "hidden")):
        keys = report[key]
        line = f"{label} {len(keys)}"
        if keys:
            line += ": " + ", ".join(report["names"][k] for k in keys[:limit])
            if len(keys) > limit:
                line += f", and {len(keys) - limit} more"
        lines.append(line)
    lines.append(f"Unchanged {report['unchanged']}")
    if report.get("unmapped"):
        lines.append("Equipment words with no rule (stored as other): "
                     + ", ".join(f"{word} ({n})" for word, n in sorted(report["unmapped"].items())))
    if report.get("compared") == "empty":
        lines.append("No admin route configured: compared with an empty catalog.")
    return "\n".join(lines)


def write(report, payloads):
    config.REPORT_DIR.mkdir(parents=True, exist_ok=True)
    text = json.dumps({k: v for k, v in report.items() if k != "pictureFiles"}, indent=1, ensure_ascii=False)
    (config.REPORT_DIR / f"import-{time.strftime('%Y%m%d-%H%M%S')}.json").write_text(text, encoding="utf-8")
    (config.REPORT_DIR / "last-report.json").write_text(text, encoding="utf-8")
    catalog = {"source": report["source"], "commit": report["commit"], "exercises": payloads,
               "pictures": report["pictureFiles"]}
    (config.REPORT_DIR / "last-catalog.json").write_text(json.dumps(catalog, ensure_ascii=False), encoding="utf-8")
