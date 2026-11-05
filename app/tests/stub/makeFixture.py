"""
Makes fixture/catalog.json and fixture/pictures/ from the importer's fixture slice (11 free-exercise-db exercises,
public domain), normalised by the importer's own rules so the stub serves what the server would. The pictures are
made up here: a plain card per picture in Superbia's colours with the exercise's name, so no upstream picture is
committed twice. Run it with the PC's own Python, which has Pillow, from the repository root:

    py -3.12 app/tests/stub/makeFixture.py
"""
import hashlib
import io
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "importer"))

import normalise  # noqa: E402

SOURCE = {"name": "free-exercise-db", "licence": "Unlicense"}
INK, VIOLET, ROYAL, TEXT = (14, 11, 20), (107, 63, 217), (142, 92, 245), (237, 231, 246)


def picture(name, index):
    image = Image.new("RGB", (480, 360), INK)
    draw = ImageDraw.Draw(image)
    for y in range(360):
        mix = y / 359
        draw.line([(0, y), (479, y)], fill=tuple(int(VIOLET[i] * (1 - mix) + INK[i] * mix) for i in range(3)))
    draw.rounded_rectangle([40, 60, 440, 300], radius=24, outline=ROYAL, width=4)
    font = ImageFont.load_default(size=28)
    draw.text((240, 160), name, fill=TEXT, font=font, anchor="mm")
    draw.text((240, 220), f"picture {index + 1}", fill=TEXT, font=ImageFont.load_default(size=20), anchor="mm")
    out = io.BytesIO()
    image.save(out, "JPEG", quality=80)
    return out.getvalue()


def main():
    rules = normalise.loadRules(REPO / "importer" / "rules")
    data = json.loads((REPO / "importer" / "tests" / "fixtures" / "exercises.json").read_text(encoding="utf-8"))
    folder = HERE / "fixture"
    pictures = folder / "pictures"
    pictures.mkdir(parents=True, exist_ok=True)
    for old in pictures.glob("*.jpg"):
        old.unlink()
    exercises = []
    for entry in sorted(data, key=lambda e: e["name"].casefold()):
        names = []
        for index, _ in enumerate(entry["images"]):
            content = picture(entry["name"], index)
            name = hashlib.sha1(content).hexdigest()[:20] + ".jpg"
            (pictures / name).write_bytes(content)
            names.append(name)
        payload, _ = normalise.normalise(entry, SOURCE, rules, names)
        payload.pop("hash")
        exercises.append({"id": len(exercises) + 1, "source": SOURCE["name"], "removed": False, **payload})
    catalog = {"version": "fixture-1", "exercises": exercises}
    (folder / "catalog.json").write_text(json.dumps(catalog, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"fixture/: {len(exercises)} exercises, {len(list(pictures.glob('*.jpg')))} pictures")


if __name__ == "__main__":
    main()
