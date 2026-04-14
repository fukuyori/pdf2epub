from __future__ import annotations

import argparse
from pathlib import Path

from .converter import ConversionOptions, convert_pdf_to_epub, inspect_pdf


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pdf2epub",
        description="Convert OCR-scanned PDF files into EPUB.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser(
        "inspect",
        help="Inspect title/issue extraction and binding heuristics.",
    )
    inspect_parser.add_argument("input_pdf", type=Path)
    inspect_parser.add_argument(
        "--binding",
        choices=("auto", "rtl", "ltr"),
        default="auto",
    )
    inspect_parser.add_argument(
        "--titles-file",
        type=Path,
        default=Path("titles.txt"),
    )

    convert_parser = subparsers.add_parser(
        "convert",
        help="Convert a PDF file into EPUB.",
    )
    convert_parser.add_argument("input_pdf", type=Path)
    convert_parser.add_argument("--output-dir", type=Path, default=Path("output"))
    convert_parser.add_argument("--output-file", type=Path)
    convert_parser.add_argument("--title")
    convert_parser.add_argument("--issue")
    convert_parser.add_argument("--author")
    convert_parser.add_argument("--language", default="ja")
    convert_parser.add_argument(
        "--binding",
        choices=("auto", "rtl", "ltr"),
        default="auto",
    )
    convert_parser.add_argument(
        "--layout",
        choices=("fixed", "reflow"),
        default="fixed",
        help="Choose fixed-layout EPUB output or reflowable page output.",
    )
    convert_parser.add_argument(
        "--ocr-mode",
        choices=("auto", "pdf-text", "tesseract", "none"),
        default="auto",
    )
    convert_parser.add_argument("--ocr-lang", default="jpn+eng")
    convert_parser.add_argument("--titles-file", type=Path, default=Path("titles.txt"))
    convert_parser.add_argument("--dpi", type=int, default=150)
    convert_parser.add_argument(
        "--no-images",
        action="store_true",
        help="Do not embed page images in the EPUB.",
    )
    convert_parser.add_argument(
        "--no-ocr-text",
        action="store_true",
        help="Do not include extracted OCR text in the EPUB.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "inspect":
        result = inspect_pdf(
            args.input_pdf,
            binding_mode=args.binding,
            title_candidates_file=args.titles_file,
        )
        print(f"Input: {args.input_pdf.resolve()}")
        print(f"Suggested title: {result.metadata.title}")
        print(f"Suggested issue: {result.metadata.issue or '-'}")
        print(f"Metadata source: {result.metadata_source}")
        print(f"Suggested binding: {result.binding.direction.value}")
        print(f"Reason: {result.binding.reason}")
        print(f"Detected TOC page: {result.toc_page or '-'}")
        print(f"Detected TOC entries: {result.toc_entries}")
        print(f"Pages: {result.page_count}")
        return 0

    if args.command == "convert":
        result = convert_pdf_to_epub(
            ConversionOptions(
                input_pdf=args.input_pdf,
                output_dir=args.output_dir,
                output_file=args.output_file,
                title=args.title,
                issue=args.issue,
                author=args.author,
                language=args.language,
                binding=args.binding,
                layout=args.layout,
                dpi=args.dpi,
                ocr_mode=args.ocr_mode,
                ocr_lang=args.ocr_lang,
                title_candidates_file=args.titles_file,
                include_images=not args.no_images,
                include_ocr_text=not args.no_ocr_text,
            )
        )
        print(f"Created: {result.output_path.resolve()}")
        print(f"Title: {result.metadata.title}")
        print(f"Issue: {result.metadata.issue or '-'}")
        print(f"Metadata source: {result.metadata_source}")
        print(f"Binding: {result.binding.direction.value}")
        print(f"Reason: {result.binding.reason}")
        print(f"Detected TOC page: {result.toc_page or '-'}")
        print(f"Detected TOC entries: {result.toc_entries}")
        print(f"Pages: {result.page_count}")
        print(f"Tesseract fallback pages: {result.tesseract_pages}")
        return 0

    parser.error("Unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
