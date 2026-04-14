from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import tempfile


def is_tesseract_available() -> bool:
    return shutil.which("tesseract") is not None


def extract_text_with_tesseract(image_bytes: bytes, languages: str = "jpn+eng") -> str:
    if not is_tesseract_available():
        return ""

    with tempfile.TemporaryDirectory(prefix="pdf2epub-") as temp_dir:
        image_path = Path(temp_dir) / "page.png"
        image_path.write_bytes(image_bytes)

        completed = subprocess.run(
            ["tesseract", str(image_path), "stdout", "-l", languages],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            return ""
        return completed.stdout.strip()
