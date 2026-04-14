import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from pdf2epub.converter import ConversionOptions, convert_pdf_to_epub


class _FakePixmap:
    def __init__(self, width: int, height: int, payload: bytes) -> None:
        self.width = width
        self.height = height
        self._payload = payload

    def tobytes(self, fmt: str) -> bytes:
        if fmt != "png":
            raise AssertionError(f"Unexpected format: {fmt}")
        return self._payload


class _FakePage:
    def __init__(self, text: str, width: int, height: int, payload: bytes) -> None:
        self._text = text
        self._width = width
        self._height = height
        self._payload = payload

    def get_text(self, kind: str) -> str:
        if kind != "text":
            raise AssertionError(f"Unexpected text kind: {kind}")
        return self._text

    def get_pixmap(self, dpi: int, alpha: bool) -> _FakePixmap:
        self.last_render = (dpi, alpha)
        return _FakePixmap(self._width, self._height, self._payload)


class _FakeDocument:
    def __init__(self, pages: list[_FakePage]) -> None:
        self._pages = pages
        self.metadata = {"title": ""}

    def __enter__(self) -> "_FakeDocument":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def __len__(self) -> int:
        return len(self._pages)

    def load_page(self, index: int) -> _FakePage:
        return self._pages[index]


class _FakeFitz:
    def __init__(self, pages: list[_FakePage]) -> None:
        self._pages = pages

    def open(self, input_pdf: Path) -> _FakeDocument:
        return _FakeDocument(self._pages)


class ConverterFixedLayoutTests(unittest.TestCase):
    def test_generated_epub_declares_fixed_layout(self) -> None:
        pages = [
            _FakePage("表紙テキスト", 1200, 1600, b"cover-png"),
            _FakePage("本文テキスト", 1200, 1600, b"page-png"),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            options = ConversionOptions(
                input_pdf=output_dir / "sample.pdf",
                output_dir=output_dir,
                title="サンプル",
                ocr_mode="pdf-text",
                title_candidates_file=None,
            )

            with patch("pdf2epub.converter._load_fitz", return_value=_FakeFitz(pages)):
                result = convert_pdf_to_epub(options)

            with zipfile.ZipFile(result.output_path) as epub:
                content_opf = epub.read("OEBPS/content.opf").decode("utf-8")
                first_page = epub.read("OEBPS/pages/page-0001.xhtml").decode("utf-8")

        self.assertIn('prefix="rendition: http://www.idpf.org/vocab/rendition/#"', content_opf)
        self.assertIn('<meta property="rendition:layout">pre-paginated</meta>', content_opf)
        self.assertIn('<meta property="rendition:orientation">auto</meta>', content_opf)
        self.assertIn('<meta property="rendition:spread">auto</meta>', content_opf)
        self.assertIn(
            '<itemref idref="page-0001" properties="rendition:layout-pre-paginated"/>',
            content_opf,
        )
        self.assertIn(
            '<meta name="viewport" content="width=1200, height=1600"/>',
            first_page,
        )
        self.assertIn('<body class="fixed-page">', first_page)

    def test_generated_epub_can_be_reflowable(self) -> None:
        pages = [
            _FakePage("表紙テキスト", 1200, 1600, b"cover-png"),
            _FakePage("本文テキスト", 1200, 1600, b"page-png"),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            options = ConversionOptions(
                input_pdf=output_dir / "sample.pdf",
                output_dir=output_dir,
                title="サンプル",
                layout="reflow",
                ocr_mode="pdf-text",
                title_candidates_file=None,
            )

            with patch("pdf2epub.converter._load_fitz", return_value=_FakeFitz(pages)):
                result = convert_pdf_to_epub(options)

            with zipfile.ZipFile(result.output_path) as epub:
                content_opf = epub.read("OEBPS/content.opf").decode("utf-8")
                first_page = epub.read("OEBPS/pages/page-0001.xhtml").decode("utf-8")

        self.assertIn('<meta property="rendition:layout">reflowable</meta>', content_opf)
        self.assertNotIn('rendition:layout-pre-paginated', content_opf)
        self.assertNotIn('rendition:orientation', content_opf)
        self.assertNotIn('rendition:spread', content_opf)
        self.assertIn('<itemref idref="page-0001"/>', content_opf)
        self.assertNotIn('<meta name="viewport"', first_page)
        self.assertIn('<body class="reflow-page">', first_page)
