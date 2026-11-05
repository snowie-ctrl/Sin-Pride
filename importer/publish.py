"""
Sends one source to plutus: first the pictures the server lacks, then the whole source as one batch, so no exercise
ever names a picture the server doesn't have.
"""
import adminApi


def publish(source, payloads, pictures):
    have = set(adminApi.get("/pictures").get("pictures", []))
    missing = sorted(set(pictures) - have)
    for name in missing:
        adminApi.putBytes(f"/pictures/{name}", pictures[name])
    answer = adminApi.post("/import", {"source": source["name"], "exercises": payloads})
    return {"picturesSent": len(missing),
            **{key: answer.get(key) for key in ("added", "changed", "unchanged", "hidden", "version")}}
