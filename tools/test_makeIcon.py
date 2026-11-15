"""makeIcon.py makes a Windows icon with every size Windows asks for, square, from the crown."""
import shutil
from pathlib import Path

from PIL import Image

import makeIcon

CROWN = Path(__file__).resolve().parent.parent / "app" / "assets" / "icons" / "prideAppIcon.png"


def test_theIconHasEverySizeAndIsSquare(tmp_path):
    shutil.copyfile(CROWN, tmp_path / "prideAppIcon.png")
    makeIcon.main(tmp_path)
    icon = Image.open(tmp_path / "pride.ico")
    assert {(16, 16), (32, 32), (48, 48), (256, 256)} <= set(icon.info["sizes"])
    icon.size = (256, 256)
    big = icon.convert("RGBA")
    # The corners are the crown's own ground, not a transparent strip from squaring it.
    assert big.getpixel((0, 0))[3] == Image.open(CROWN).convert("RGBA").getpixel((0, 0))[3]
