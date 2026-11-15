"""
The catalog importer, run by hand from the repository root (spec §2):

    importer/.venv/Scripts/python.exe importer/main.py

It fetches each source at its pinned commit, normalises it, and prints the change report against the server (or an
empty catalog with no server configured). It stops there unless importer/.env says PUBLISH=on. It also stops,
publishing nothing, when the upstream file doesn't look as expected, a picture isn't a JPEG, or publishing would hide
more than 10% of the catalog. Exit codes: 0 done or a dry run, 2 the upstream shape, 3 the guard, 4 publishing asked
for but not configured, 5 the server refused or failed, 6 fetching failed.
"""
import sys
from collections import Counter

import adminApi
import config
import fetch
import net
import normalise
import publish
import report


def run(out=print):
    try:
        rules = normalise.loadRules()
        sources = fetch.loadSources()
        state = adminApi.get("/state") if adminApi.configured() else None
        for source in sources:
            code = runSource(source, rules, state, out)
            if code:
                return code
    except (fetch.SourceError, net.FetchError) as error:
        out(f"Fetching failed: {error}; nothing was published")
        return 6
    except adminApi.AdminError as error:
        out(f"The server could not be asked: {error}; nothing was published")
        return 5
    return 0


def runSource(source, rules, state, out):
    data = fetch.fetchExercises(source)
    problem = normalise.shapeProblem(data, rules)
    if problem:
        out(f"{source['name']}: the upstream file does not look as expected ({problem}); nothing was published")
        return 2
    pictureBytes = fetch.fetchPictures(source, [path for e in data for path in e["images"]])
    notJpeg = sorted(path for path, data in pictureBytes.items() if not normalise.isJpeg(data))
    if notJpeg:
        out(f"{source['name']}: {notJpeg[0]} is not a JPEG; nothing was published")
        return 2
    names = {path: normalise.pictureName(data) for path, data in pictureBytes.items()}

    payloads, unmapped = [], Counter()
    for entry in data:
        payload, word = normalise.normalise(entry, source, rules, [names[path] for path in entry["images"]])
        payloads.append(payload)
        if word:
            unmapped[word] += 1

    summary = report.changeReport(payloads, report.stateFor(state, source["name"]))
    summary.update({
        "source": source["name"], "commit": source["commit"], "exercises": len(payloads),
        "pictures": len(set(names.values())), "unmapped": dict(unmapped),
        "compared": "server" if state is not None else "empty", "mode": config.PUBLISH,
        "pictureFiles": {names[path]: f"{source['name']}/{source['commit']}/{source['pictures']}/{path}"
                         for path in names},
    })
    out(report.render(summary))

    problem = report.guardProblem(summary, config.HIDE_GUARD)
    if problem:
        out(problem)
        report.write(summary, payloads)
        return 3
    if config.PUBLISH != "on":
        out("Dry run: nothing was sent. PUBLISH=on in importer/.env publishes.")
        report.write(summary, payloads)
        return 0
    if not adminApi.configured():
        out("PUBLISH=on needs ADMIN_BASE and ADMIN_TOKEN in importer/.env; nothing was sent.")
        return 4
    try:
        result = publish.publish(source, payloads, {names[path]: pictureBytes[path] for path in names})
    except adminApi.AdminError as error:
        out(f"Publishing failed: {error}")
        summary["publish"] = {"error": str(error)}
        report.write(summary, payloads)
        return 5
    summary["publish"] = result
    out(f"Published: {result['added']} added, {result['changed']} changed, {result['hidden']} hidden, "
        f"{result['picturesSent']} pictures sent; catalog version {str(result['version'])[:12]}")
    report.write(summary, payloads)
    return 0


if __name__ == "__main__":
    sys.exit(run())
