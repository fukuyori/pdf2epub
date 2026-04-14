from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape
from pathlib import Path
import textwrap
import uuid
import zipfile

from .binding import BindingDecision, resolve_binding
from .metadata import (
    ExtractedMetadata,
    infer_metadata,
    load_title_candidates,
    sanitize_filename,
)
from .ocr import extract_text_with_tesseract, is_tesseract_available
from .toc import detect_toc_page, parse_toc_entries


CONTAINER_XML = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""

BOOK_CSS = """
html, body {
  margin: 0;
  padding: 0;
  font-family: serif;
  line-height: 1.6;
}
body {
  padding: 1rem;
}
.page-image {
  display: block;
  width: 100%;
  height: auto;
  margin: 0 auto 1rem;
}
.ocr-text {
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 0.95rem;
}
.empty-text {
  color: #666;
  font-style: italic;
}
nav ol {
  padding-left: 1.25rem;
}
"""


@dataclass(frozen=True)
class ConversionOptions:
    input_pdf: Path
    output_dir: Path
    output_file: Path | None = None
    title: str | None = None
    issue: str | None = None
    author: str | None = None
    language: str = "ja"
    binding: str = "auto"
    dpi: int = 150
    ocr_mode: str = "auto"
    ocr_lang: str = "jpn+eng"
    title_candidates_file: Path | None = Path("titles.txt")
    include_images: bool = True
    include_ocr_text: bool = True


@dataclass(frozen=True)
class InspectionResult:
    metadata: ExtractedMetadata
    metadata_source: str
    binding: BindingDecision
    page_count: int
    toc_page: int | None = None
    toc_entries: int = 0


@dataclass(frozen=True)
class ConversionResult:
    output_path: Path
    metadata: ExtractedMetadata
    metadata_source: str
    binding: BindingDecision
    page_count: int
    tesseract_pages: int
    toc_page: int | None = None
    toc_entries: int = 0


def _load_fitz():
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError(
            "PyMuPDF is required. Install it with `pip install PyMuPDF`."
        ) from exc
    return fitz


def _normalized_text(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.splitlines()).strip()


def _extract_cover_text(page, ocr_mode: str, ocr_lang: str) -> str:
    if ocr_mode not in {"auto", "tesseract"}:
        return ""
    if not is_tesseract_available():
        return ""
    pix = page.get_pixmap(dpi=150, alpha=False)
    return _normalized_text(extract_text_with_tesseract(pix.tobytes("png"), ocr_lang))


def _extract_preview_text(page, ocr_mode: str, ocr_lang: str) -> str:
    text = _normalized_text(page.get_text("text"))
    if text:
        return text
    return _extract_cover_text(page, ocr_mode, ocr_lang)


def inspect_pdf(
    input_pdf: Path,
    binding_mode: str = "auto",
    title_candidates_file: Path | None = Path("titles.txt"),
) -> InspectionResult:
    fitz = _load_fitz()
    title_candidates = load_title_candidates(title_candidates_file)

    with fitz.open(input_pdf) as doc:
        samples = []
        preview_texts: list[str] = []
        cover_text = ""
        for page_index in range(min(len(doc), 12)):
            page = doc.load_page(page_index)
            sample = _extract_preview_text(page, "auto", "jpn+eng")
            preview_texts.append(sample)
            if sample and page_index < 5:
                samples.append(sample[:1000])
            if page_index == 0:
                cover_text = sample
        toc_page_index, toc_text = detect_toc_page(preview_texts)
        toc_entries = parse_toc_entries(toc_text) if toc_page_index is not None else []

        metadata_decision = infer_metadata(
            input_pdf.name,
            pdf_title=doc.metadata.get("title", ""),
            cover_text=cover_text,
            title_candidates=title_candidates,
        )
        binding = resolve_binding(
            binding_mode,
            metadata_decision.metadata.original_stem,
            samples + ([cover_text] if cover_text else []),
            language_hint="ja",
            pdf_creator=doc.metadata.get("creator", ""),
            image_only=not bool(samples),
        )
        return InspectionResult(
            metadata=metadata_decision.metadata,
            metadata_source=metadata_decision.source,
            binding=binding,
            page_count=len(doc),
            toc_page=(toc_page_index + 1) if toc_page_index is not None else None,
            toc_entries=len(toc_entries),
        )


def convert_pdf_to_epub(options: ConversionOptions) -> ConversionResult:
    if not options.include_images and not options.include_ocr_text:
        raise ValueError("At least one of include_images/include_ocr_text must be enabled.")

    fitz = _load_fitz()
    options.output_dir.mkdir(parents=True, exist_ok=True)
    title_candidates = load_title_candidates(options.title_candidates_file)

    with fitz.open(options.input_pdf) as doc:
        text_samples = []
        preview_texts: list[str] = []
        cover_text = ""
        for page_index in range(min(len(doc), 12)):
            page = doc.load_page(page_index)
            sample = _extract_preview_text(page, options.ocr_mode, options.ocr_lang)
            preview_texts.append(sample)
            if sample and page_index < 5:
                text_samples.append(sample[:1000])
            if page_index == 0:
                cover_text = sample

        toc_page_index, toc_text = detect_toc_page(preview_texts)
        toc_entries = parse_toc_entries(toc_text) if toc_page_index is not None else []

        metadata_decision = infer_metadata(
            options.input_pdf.name,
            pdf_title=doc.metadata.get("title", ""),
            cover_text=cover_text,
            title_candidates=title_candidates,
        )
        binding = resolve_binding(
            options.binding,
            metadata_decision.metadata.original_stem,
            text_samples + ([cover_text] if cover_text else []),
            language_hint=options.language,
            pdf_creator=doc.metadata.get("creator", ""),
            image_only=not bool(text_samples),
        )
        resolved_title = options.title or metadata_decision.metadata.title
        resolved_issue = options.issue or metadata_decision.metadata.issue
        resolved_metadata = ExtractedMetadata(
            title=resolved_title,
            issue=resolved_issue,
            original_stem=metadata_decision.metadata.original_stem,
        )

        output_path = (
            options.output_file
            if options.output_file is not None
            else options.output_dir / f"{sanitize_filename(options.input_pdf.stem)}.epub"
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)

        identifier = f"urn:uuid:{uuid.uuid4()}"
        modified = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        title_for_opf = escape(
            f"{resolved_title} {resolved_issue}".strip() if resolved_issue else resolved_title
        )
        author_for_opf = escape(options.author) if options.author else ""
        manifest_items: list[str] = [
            '<item id="css" href="styles/book.css" media-type="text/css"/>',
            '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
        ]
        spine_items: list[str] = []
        nav_entries: list[str] = ['<li><a href="pages/page-0001.xhtml">表紙</a></li>']
        tesseract_pages = 0

        with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as epub:
            epub.writestr(
                zipfile.ZipInfo("mimetype"),
                "application/epub+zip",
                compress_type=zipfile.ZIP_STORED,
            )
            epub.writestr("META-INF/container.xml", CONTAINER_XML)
            epub.writestr("OEBPS/styles/book.css", BOOK_CSS)

            for page_number in range(len(doc)):
                page = doc.load_page(page_number)
                image_name = f"images/page-{page_number + 1:04d}.png"
                xhtml_name = f"pages/page-{page_number + 1:04d}.xhtml"
                page_id = f"page-{page_number + 1:04d}"

                pix = page.get_pixmap(dpi=options.dpi, alpha=False)
                image_bytes = pix.tobytes("png")
                pdf_text = _normalized_text(page.get_text("text"))
                final_text = pdf_text

                if options.ocr_mode == "tesseract":
                    final_text = _normalized_text(
                        extract_text_with_tesseract(image_bytes, options.ocr_lang)
                    )
                    if final_text:
                        tesseract_pages += 1
                elif options.ocr_mode == "auto" and not final_text:
                    extracted = extract_text_with_tesseract(image_bytes, options.ocr_lang)
                    if extracted:
                        final_text = _normalized_text(extracted)
                        tesseract_pages += 1
                elif options.ocr_mode == "none":
                    final_text = ""
                elif options.ocr_mode == "pdf-text":
                    final_text = pdf_text

                if options.include_images:
                    epub.writestr(f"OEBPS/{image_name}", image_bytes)
                    image_properties = ' properties="cover-image"' if page_number == 0 else ""
                    manifest_items.append(
                        f'<item id="img-{page_number + 1:04d}" href="{image_name}" media-type="image/png"{image_properties}/>'
                    )

                xhtml_parts = [
                    "<?xml version='1.0' encoding='utf-8'?>",
                    f'<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="{escape(options.language)}">',
                    "<head>",
                    f"<title>{escape(resolved_title)} - {page_number + 1}</title>",
                    '<link rel="stylesheet" type="text/css" href="../styles/book.css"/>',
                    "</head>",
                    "<body>",
                ]
                if options.include_images:
                    xhtml_parts.append(
                        f'<img class="page-image" src="../{image_name}" alt="Page {page_number + 1}"/>'
                    )
                if options.include_ocr_text:
                    if final_text:
                        xhtml_parts.append(f'<pre class="ocr-text">{escape(final_text)}</pre>')
                xhtml_parts.extend(["</body>", "</html>"])
                epub.writestr(f"OEBPS/{xhtml_name}", "\n".join(xhtml_parts))

                manifest_items.append(
                    f'<item id="{page_id}" href="{xhtml_name}" media-type="application/xhtml+xml"/>'
                )
                spine_items.append(f'<itemref idref="{page_id}"/>')
            if toc_page_index is not None:
                toc_href = "pages/detected-toc.xhtml"
                toc_sections = []
                for idx, entry in enumerate(toc_entries, 1):
                    page_label = f" p.{entry.printed_page}" if entry.printed_page is not None else ""
                    toc_sections.append(
                        f'<li id="toc-entry-{idx}">{escape(entry.title)}{escape(page_label)}</li>'
                    )
                if not toc_sections:
                    toc_sections.append('<li>目次ページは見つかりましたが、項目の抽出はできませんでした。</li>')

                toc_page_number = toc_page_index + 1
                detected_toc_xhtml = textwrap.dedent(
                    f"""\
                    <?xml version="1.0" encoding="utf-8"?>
                    <html xmlns="http://www.w3.org/1999/xhtml" xml:lang="{escape(options.language)}">
                      <head>
                        <title>{title_for_opf} - 目次</title>
                        <link rel="stylesheet" type="text/css" href="../styles/book.css"/>
                      </head>
                      <body>
                        <h1>目次</h1>
                        <p>PDF の {toc_page_number} ページ目から検出した目次です。</p>
                        <ol>
                          {"".join(toc_sections)}
                        </ol>
                        <p><a href="page-{toc_page_number:04d}.xhtml">元の目次ページを開く</a></p>
                      </body>
                    </html>
                    """
                )
                epub.writestr(f"OEBPS/{toc_href}", detected_toc_xhtml)
                manifest_items.append(
                    f'<item id="detected-toc" href="{toc_href}" media-type="application/xhtml+xml"/>'
                )
                if spine_items:
                    spine_items.insert(1, '<itemref idref="detected-toc"/>')
                else:
                    spine_items.append('<itemref idref="detected-toc"/>')

                toc_nav_entries = ['<li><a href="pages/page-0001.xhtml">表紙</a></li>']
                toc_nav_entries.append(f'<li><a href="{toc_href}">目次</a></li>')
                toc_nav_entries.extend(
                    f'<li><a href="{toc_href}#toc-entry-{idx}">{escape(entry.title)}</a></li>'
                    for idx, entry in enumerate(toc_entries, 1)
                )
                nav_entries = toc_nav_entries

            nav_xhtml = textwrap.dedent(
                f"""\
                <?xml version="1.0" encoding="utf-8"?>
                <html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="{escape(options.language)}">
                  <head>
                    <title>{title_for_opf}</title>
                    <link rel="stylesheet" type="text/css" href="styles/book.css"/>
                  </head>
                  <body>
                    <nav epub:type="toc" id="toc">
                      <h1>{title_for_opf}</h1>
                      <ol>
                        {"".join(nav_entries)}
                      </ol>
                    </nav>
                  </body>
                </html>
                """
            )
            epub.writestr("OEBPS/nav.xhtml", nav_xhtml)

            metadata_lines = [
                f"<dc:identifier id=\"pub-id\">{identifier}</dc:identifier>",
                f"<dc:title>{title_for_opf}</dc:title>",
                f"<dc:language>{escape(options.language)}</dc:language>",
                f"<meta property=\"dcterms:modified\">{modified}</meta>",
            ]
            if options.include_images:
                metadata_lines.append('<meta name="cover" content="img-0001"/>')
            if author_for_opf:
                metadata_lines.append(f"<dc:creator>{author_for_opf}</dc:creator>")

            content_opf = textwrap.dedent(
                f"""\
                <?xml version="1.0" encoding="utf-8"?>
                <package xmlns="http://www.idpf.org/2007/opf" xmlns:dc="http://purl.org/dc/elements/1.1/" version="3.0" unique-identifier="pub-id">
                  <metadata>
                    {' '.join(metadata_lines)}
                  </metadata>
                  <manifest>
                    {' '.join(manifest_items)}
                  </manifest>
                  <spine page-progression-direction="{binding.direction.value}">
                    {' '.join(spine_items)}
                  </spine>
                </package>
                """
            )
            epub.writestr("OEBPS/content.opf", content_opf)

        return ConversionResult(
            output_path=output_path,
            metadata=resolved_metadata,
            metadata_source=metadata_decision.source,
            binding=binding,
            page_count=len(doc),
            tesseract_pages=tesseract_pages,
            toc_page=(toc_page_index + 1) if toc_page_index is not None else None,
            toc_entries=len(toc_entries),
        )
