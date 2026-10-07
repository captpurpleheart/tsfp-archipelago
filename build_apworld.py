"""Package the world as timesplitters_future_perfect.apworld (a zip of the world folder).

Run:  py build_apworld.py
Then double-click the .apworld, or copy it into Archipelago's custom_worlds folder.
"""
import pathlib
import zipfile

ROOT = pathlib.Path(__file__).parent
WORLD = ROOT / "timesplitters_future_perfect"
OUT = ROOT / "timesplitters_future_perfect.apworld"

with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
    for path in sorted(WORLD.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts:
            z.write(path, path.relative_to(ROOT).as_posix())
print(f"Wrote {OUT.name}")
