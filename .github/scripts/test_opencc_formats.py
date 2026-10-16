"""Regression checks for OpenCC dictionary formats and configuration references."""
import json
from pathlib import Path
import tempfile
import unittest

from build_hant import read, resolve_opencc_formats, validate, write


class OpenCCFormatTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[2])
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = self.root / "opencc/wanxiang_t2s.json"
        self.node = {"type": "ocd2", "file": "wanxiang/TSPhrases.ocd2"}
        write(self.config, json.dumps({
            "segmentation": {"type": "mmseg", "dict": {"type": "group", "dicts": [self.node]}},
            "conversion_chain": [{"dict": self.node}],
        }))

    def test_missing_binary_uses_text_in_nested_references(self):
        text = self.root / "opencc/wanxiang/TSPhrases.txt"
        write(text, "測試\t测试\n")
        resolve_opencc_formats(self.root)
        config = json.loads(read(self.config))
        expected = {"type": "text", "file": "wanxiang/TSPhrases.txt"}
        self.assertEqual(config["segmentation"]["dict"]["dicts"][0], expected)
        self.assertEqual(config["conversion_chain"][0]["dict"], expected)
        self.assertEqual(read(text), "測試\t测试\n")
        self.assertFalse(text.with_suffix(".ocd2").exists())
        validate(self.root)
        before = read(self.config)
        resolve_opencc_formats(self.root)
        self.assertEqual(read(self.config), before)

    def test_existing_binary_keeps_original_config(self):
        write(self.root / "opencc/wanxiang/TSPhrases.ocd2", "existing binary")
        write(self.root / "opencc/wanxiang/TSPhrases.txt", "測試\t测试\n")
        before = read(self.config)
        resolve_opencc_formats(self.root)
        self.assertEqual(read(self.config), before)
        validate(self.root)

    def test_missing_dictionary_is_still_rejected(self):
        before = read(self.config)
        resolve_opencc_formats(self.root)
        self.assertEqual(read(self.config), before)
        with self.assertRaisesRegex(ValueError, "Missing OpenCC dictionary"):
            validate(self.root)


if __name__ == "__main__":
    unittest.main()
