import unittest

from pdf2epub.metadata import build_output_stem, extract_issue, infer_metadata


class MetadataTests(unittest.TestCase):
    def test_extract_issue_from_text(self) -> None:
        self.assertEqual(extract_issue("月刊サンプル 2026年4月号"), "2026年4月号")

    def test_build_output_stem_joins_title_and_issue(self) -> None:
        self.assertEqual(build_output_stem("宇宙兄弟", "第42巻"), "宇宙兄弟_第42巻")

    def test_infer_metadata_matches_title_candidates(self) -> None:
        decision = infer_metadata(
            "20260315135121.pdf",
            cover_text="Newton\n2025 4\nニュートン",
            title_candidates=["月間統計", "Newton", "科学"],
        )
        self.assertEqual(decision.metadata.title, "Newton")
        self.assertEqual(decision.metadata.issue, "2025 4")
        self.assertEqual(decision.source, "title-candidates")

    def test_infer_metadata_allows_fuzzy_candidate_match(self) -> None:
        decision = infer_metadata(
            "20260315185939.pdf",
            cover_text="月刊統計\n2025 10",
            title_candidates=["月間統計"],
        )
        self.assertEqual(decision.metadata.title, "月間統計")

    def test_infer_metadata_does_not_parse_filename(self) -> None:
        decision = infer_metadata("月刊サンプル 2026年4月号.pdf")
        self.assertEqual(decision.metadata.title, "月刊サンプル 2026年4月号")
        self.assertIsNone(decision.metadata.issue)
        self.assertEqual(decision.source, "input-stem-fallback")
