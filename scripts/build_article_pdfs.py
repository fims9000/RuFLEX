from __future__ import annotations

import subprocess
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTICLE_DIR = ROOT / "docs/article"

PDF_TARGETS = (
    ARTICLE_DIR / "paper_draft.docx",
    ARTICLE_DIR / "shablon_dokladov_illustrated.docx",
    ARTICLE_DIR / "conference_template_illustrated_en.docx",
    ARTICLE_DIR / "rinc_draft.docx",
)


def main() -> None:
    generated = build_article_pdfs()
    for path in generated:
        print(path)


def build_article_pdfs() -> list[Path]:
    generated: list[Path] = []
    for source in PDF_TARGETS:
        if not source.exists():
            raise FileNotFoundError(f"Cannot build PDF because source document is missing: {source}")
        _convert_to_pdf(source, ARTICLE_DIR)
        generated.append(source.with_suffix(".pdf"))
    return generated


def _convert_to_pdf(source: Path, output_dir: Path) -> None:
    command = [
        "libreoffice",
        "--headless",
        "--convert-to",
        "pdf",
        "--outdir",
        str(output_dir),
        str(source),
    ]
    last_error: subprocess.CalledProcessError | None = None
    for attempt in range(1, 4):
        try:
            subprocess.run(command, check=True, cwd=ROOT)
            return
        except subprocess.CalledProcessError as error:
            last_error = error
            if attempt == 3:
                raise
            time.sleep(1.0)
    if last_error is not None:
        raise last_error


if __name__ == "__main__":
    main()
