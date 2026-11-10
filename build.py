"""Create an installable Anki add-on archive with files at the archive root."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

root = Path(__file__).resolve().parent
source = root / "contextual_explanations"
destination = root / "dist" / "ai-contextual-explanations.ankiaddon"
destination.parent.mkdir(exist_ok=True)
with ZipFile(destination, "w", ZIP_DEFLATED) as archive:
    for path in source.rglob("*"):
        if not path.is_file() or "__pycache__" in path.parts or "user_files" in path.parts:
            continue
        archive.write(path, path.relative_to(source))
print(destination)
