"""
Fetching a source at its pinned commit (sources.json) through importer/cache/<source>/<commit>/. The commit pins the
content, so a cached file never goes stale and a second run downloads nothing. Pictures are fetched a few at a time.
"""
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor

import config
import net

COMMIT = re.compile(r"[0-9a-f]{40}")
REQUIRED = ("name", "repo", "commit", "licence", "data", "pictures")


class SourceError(Exception):
    pass


def loadSources(path=None):
    sources = json.loads((path or config.SOURCES_FILE).read_text(encoding="utf-8"))
    if not isinstance(sources, list) or not sources:
        raise SourceError("sources.json must list at least one source")
    for source in sources:
        missing = [key for key in REQUIRED if not isinstance(source.get(key), str) or not source[key]]
        if missing:
            raise SourceError(f"a source lacks {', '.join(missing)}")
        if not COMMIT.fullmatch(source["commit"]):
            raise SourceError(f"{source['name']}: commit must be a full 40-hex commit, so the content is pinned")
    return sources


def rawUrl(source, path):
    return f"https://raw.githubusercontent.com/{source['repo']}/{source['commit']}/{path}"


def cachePath(source, path):
    return config.CACHE_DIR / source["name"] / source["commit"] / path


def cached(source, path):
    """The file at `path` in the source's pinned commit: from the cache, or fetched into it. Written aside and moved
    into place, so a run cut short never leaves half a file that a later run would trust."""
    target = cachePath(source, path)
    if target.is_file():
        return target.read_bytes()
    data = net.fetchBytes(rawUrl(source, path))
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + ".part")
    partial.write_bytes(data)
    os.replace(partial, target)
    return data


def fetchExercises(source):
    try:
        return json.loads(cached(source, source["data"]).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SourceError(f"{source['name']}: {source['data']} is not JSON ({error})")


def fetchPictures(source, paths):
    """{path: bytes} for each distinct picture path (relative to the source's picture folder)."""
    unique = sorted(set(paths))
    with ThreadPoolExecutor(max_workers=config.PARALLEL) as pool:
        data = list(pool.map(lambda path: cached(source, f"{source['pictures']}/{path}"), unique))
    return dict(zip(unique, data))
