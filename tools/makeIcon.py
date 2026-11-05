"""
Makes app/assets/icons/pride.ico (the .exe's icon, at every size Windows asks for) from the owner's crown,
app/assets/icons/prideAppIcon.png. The crown is squared on its own ground colour, so no size shows a strip. Run it
with the PC's own Python, which has Pillow:  py -3.12 tools/makeIcon.py
"""
import sys
from pathlib import Path

from PIL import Image

ICONS = Path(__file__).resolve().parent.parent / "app" / "assets" / "icons"
SIZES = [(16, 16), (20, 20), (24, 24), (32, 32), (40, 40), (48, 48), (64, 64), (128, 128), (256, 256)]


def main(folder=ICONS):
    folder = Path(folder)
    crown = Image.open(folder / "prideAppIcon.png").convert("RGBA")
    side = max(crown.size)
    square = Image.new("RGBA", (side, side), crown.getpixel((0, 0)))
    square.paste(crown, ((side - crown.width) // 2, (side - crown.height) // 2), crown)
    square.resize((256, 256), Image.LANCZOS).save(folder / "pride.ico", sizes=SIZES)


if __name__ == "__main__":
    main(*sys.argv[1:])
