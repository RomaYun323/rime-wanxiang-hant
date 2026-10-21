"""檢查 OpenCC 詞典格式與設定引用的迴歸測試。"""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from build_hant import (copy_custom_opencc_configs, prepare_release_opencc,
                        prepare_source_opencc, read, validate, write)


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

    def test_release_compiles_standard_dictionaries_and_preserves_custom_text(self):
        self.config.unlink()
        config = self.root / "opencc/wanxiang_t2tw.json"
        variants = {"type": "text", "file": "wanxiang/TWVariants.txt"}
        phrases = {"type": "text", "file": "wanxiang/Custom_TSPhrases.txt"}
        emoji = {"type": "text", "file": "wanxiang/Custom_Emoji.txt"}
        write(config, json.dumps({
            "segmentation": {"type": "mmseg", "dict": {
                "type": "group", "dicts": [variants, phrases, emoji]}},
            "conversion_chain": [{"dict": variants}],
        }))
        text = self.root / "opencc/wanxiang/TWVariants.txt"
        write(text, "臺\t台 臺\n")
        phrases_text = self.root / "opencc/wanxiang/Custom_TSPhrases.txt"
        write(phrases_text, "乾隆\t乾隆\n")
        emoji_text = self.root / "opencc/wanxiang/Custom_Emoji.txt"
        write(emoji_text, "測試\t🧪\n")

        def compile_dictionary(command, check):
            self.assertTrue(check)
            output = Path(command[command.index("-o") + 1])
            write(output, "compiled")

        with patch("build_hant.subprocess.run", side_effect=compile_dictionary):
            prepare_release_opencc(self.root)

        expected = {"type": "ocd2", "file": "wanxiang/TWVariants.ocd2"}
        result = json.loads(read(config))
        self.assertEqual(result["segmentation"]["dict"]["dicts"][0], expected)
        self.assertEqual(result["segmentation"]["dict"]["dicts"][1], {
            "type": "text", "file": "wanxiang/Custom_TSPhrases.txt"})
        self.assertEqual(result["segmentation"]["dict"]["dicts"][2], {
            "type": "text", "file": "wanxiang/Custom_Emoji.txt"})
        self.assertEqual(result["conversion_chain"][0]["dict"], expected)
        self.assertFalse(text.exists())
        self.assertTrue(phrases_text.exists())
        self.assertTrue(emoji_text.exists())
        self.assertTrue(text.with_suffix(".ocd2").is_file())
        self.assertFalse(phrases_text.with_suffix(".ocd2").exists())
        self.assertFalse(emoji_text.with_suffix(".ocd2").exists())
        validate(self.root)

    def test_source_decodes_binaries_and_rewrites_config(self):
        self.config.unlink()
        config = self.root / "opencc/wanxiang_t2hk.json"
        node = {"type": "ocd2", "file": "wanxiang/HKVariants.ocd2"}
        write(config, json.dumps({
            "segmentation": {"type": "mmseg", "dict": node},
            "conversion_chain": [{"dict": node}],
        }))
        compiled = self.root / "opencc/wanxiang/HKVariants.ocd2"
        write(compiled, "compiled")

        def decode_dictionary(command, check):
            self.assertTrue(check)
            output = Path(command[command.index("-o") + 1])
            write(output, "香港\t香港\n")

        with patch("build_hant.subprocess.run", side_effect=decode_dictionary):
            prepare_source_opencc(self.root)

        expected = {"type": "text", "file": "wanxiang/HKVariants.txt"}
        result = json.loads(read(config))
        self.assertEqual(result["segmentation"]["dict"], expected)
        self.assertEqual(result["conversion_chain"][0]["dict"], expected)
        self.assertFalse(compiled.exists())
        self.assertTrue(compiled.with_suffix(".txt").is_file())
        validate(self.root)

    def test_custom_configs_are_copied_verbatim(self):
        custom = self.root / "custom_configs"
        output = self.root / "output"
        names = ("wanxiang_t2s.json", "wanxiang_t2hk.json", "wanxiang_t2tw.json")
        for index, name in enumerate(names):
            content = '{\n  "format": "text",\n  "index": ' + str(index) + '\n}\n'
            write(custom / "opencc" / name, content)
        (output / "opencc").mkdir(parents=True)

        copy_custom_opencc_configs(custom, output)

        for name in names:
            self.assertEqual((output / "opencc" / name).read_bytes(),
                             (custom / "opencc" / name).read_bytes())

    def test_source_validation_accepts_text_for_future_release_binary(self):
        write(self.root / "opencc/wanxiang/TSPhrases.txt", "測試\t测试\n")

        validate(self.root, allow_release_sources=True)

        with self.assertRaisesRegex(ValueError, "Missing OpenCC dictionary"):
            validate(self.root)


if __name__ == "__main__":
    unittest.main()
