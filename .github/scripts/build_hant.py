"""從兩份上游快照建立獨立的繁體基礎方案。"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import zipfile

import yaml


def read(path):
    return path.read_text(encoding="utf-8-sig")


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def convert(text, config="s2t.json"):
    with tempfile.TemporaryDirectory() as folder:
        source, target = Path(folder) / "in.txt", Path(folder) / "out.txt"
        write(source, text)
        subprocess.run(["opencc", "-i", str(source), "-o", str(target), "-c", config], check=True)
        return read(target)


def yaml_header(path):
    return yaml.safe_load(read(path).split("\n...", 1)[0])


def supply_opencc_dictionaries(source, target):
    """為萬象缺少的標準詞典補上文字來源。"""
    for name in ("TSCharacters", "TSPhrases", "HKVariants", "TWVariants"):
        text = target / (name + ".txt")
        if text.is_file():
            continue
        supplied = source / text.name
        if not supplied.is_file():
            raise ValueError(f"Missing OpenCC source: {supplied}")
        shutil.copy2(supplied, text)


def convert_dictionary(source, target):
    # 僅轉換文字；編碼、詞頻及其他欄位皆逐位元組保持不變。
    header, body = read(source).split("\n...", 1)
    lines = body.splitlines(keepends=True)
    indices = [i for i, line in enumerate(lines) if "\t" in line and not line.startswith("#")]
    texts = [lines[i].split("\t", 1)[0] for i in indices]
    converted = convert("\n".join(texts) + "\n").splitlines()
    if len(converted) != len(texts):
        raise ValueError(f"Dictionary row count changed: {source}")
    for i, text in zip(indices, converted):
        lines[i] = text + "\t" + lines[i].split("\t", 1)[1]
    write(target, header + "\n..." + "".join(lines))


def rewrite_opencc_format(root, source_type, target_type):
    """對應的目標檔存在時，改寫詞典格式引用。"""
    suffixes = {"text": ".txt", "ocd2": ".ocd2"}
    source_suffix = suffixes[source_type]
    target_suffix = suffixes[target_type]

    def rewrite(node):
        if isinstance(node, dict):
            filename = node.get("file")
            if node.get("type") == source_type and filename and filename.endswith(source_suffix):
                target_name = filename[:-len(source_suffix)] + target_suffix
                if (root / "opencc" / target_name).is_file():
                    node.update(type=target_type, file=target_name)
            for value in node.values():
                rewrite(value)
        elif isinstance(node, list):
            for value in node:
                rewrite(value)

    for path in (root / "opencc").glob("*.json"):
        config = json.loads(read(path))
        rewrite(config)
        write(path, json.dumps(config, ensure_ascii=False, indent=2) + "\n")


def prepare_source_opencc(root):
    """讓倉庫詞典維持可讀文字格式，並讓 JSON 指向文字檔。"""
    dictionary_root = root / "opencc/wanxiang"
    for compiled in dictionary_root.glob("*.ocd2"):
        text = compiled.with_suffix(".txt")
        if not text.is_file():
            subprocess.run(["opencc_dict", "-i", str(compiled), "-o", str(text),
                            "-f", "ocd2", "-t", "text"], check=True)
        if not text.is_file() or text.stat().st_size == 0:
            raise ValueError(f"OpenCC did not decode dictionary: {compiled}")
        compiled.unlink()
    rewrite_opencc_format(root, "ocd2", "text")


def prepare_release_opencc(root):
    """編譯一般文字詞典，並保留 Release 內的自訂文字詞典。"""
    dictionary_root = root / "opencc/wanxiang"
    all_texts = list(dictionary_root.glob("*.txt"))
    if not all_texts:
        raise ValueError(f"No OpenCC text dictionaries found: {dictionary_root}")
    preserved_texts = {"Custom_Emoji.txt", "Custom_TSPhrases.txt"}
    compiled_texts = [text for text in all_texts if text.name not in preserved_texts]
    for text in compiled_texts:
        normalized = []
        for line in read(text).splitlines():
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            if "\t" in line:
                key, values = line.split("\t", 1)
                line = key + "\t" + values.replace("\t", " ")
            normalized.append(line)
        write(text, "\n".join(normalized) + "\n")
        compiled = text.with_suffix(".ocd2")
        compiled.unlink(missing_ok=True)
        subprocess.run(["opencc_dict", "-i", str(text), "-o", str(compiled),
                        "-f", "text", "-t", "ocd2"], check=True)
        if not compiled.is_file() or compiled.stat().st_size == 0:
            raise ValueError(f"OpenCC did not compile dictionary: {text}")
    rewrite_opencc_format(root, "text", "ocd2")
    for text in compiled_texts:
        text.unlink()


def copy_custom_opencc_configs(custom, root):
    """將維護中的繁轉設定原樣複製到輸出目錄。"""
    for name in ("wanxiang_t2s.json", "wanxiang_t2hk.json", "wanxiang_t2tw.json"):
        shutil.copy2(custom / "opencc" / name, root / "opencc" / name)


def remove_upstream_st_dictionaries(root):
    """移除輸出方案不使用的上游簡轉繁詞典。"""
    dictionary_root = root / "opencc/wanxiang"
    for name in ("Custom_STPhrases.txt", "STCharacters.txt", "STPhrases.txt"):
        (dictionary_root / name).unlink(missing_ok=True)


def validate(root, allow_release_sources=False):
    for path in root.glob("*.dict.yaml"):
        for table in yaml_header(path).get("import_tables", []):
            if not (root / (table + ".dict.yaml")).is_file():
                raise ValueError(f"Missing imported dictionary: {path.name}: {table}")
    for path in root.glob("*.schema.yaml"):
        data = yaml.safe_load(read(path))
        for dep in data.get("schema", {}).get("dependencies", []):
            if not (root / (dep + ".schema.yaml")).is_file():
                raise ValueError(f"Missing schema: {dep}")
        for node in data.values():
            if isinstance(node, dict) and "opencc_config" in node:
                if node["opencc_config"] in {"wanxiang_s2t.json", "wanxiang_s2hk.json", "wanxiang_s2tw.json"}:
                    continue
                if not (root / "opencc" / node["opencc_config"]).is_file():
                    raise ValueError(f"Missing OpenCC config: {node}")
    for path in root.glob("*.custom.yaml"):
        patch = yaml.safe_load(read(path)).get("patch", {})
        schema = root / path.name.replace(".custom.yaml", ".schema.yaml")
        data = yaml.safe_load(read(schema)) if schema.is_file() else {}
        for filter_name in patch.get("engine/filters", []):
            if filter_name.startswith("simplifier@"):
                name = filter_name.split("@", 1)[1]
                node = patch.get(name, data.get(name))
                if not isinstance(node, dict) or "opencc_config" not in node:
                    raise ValueError(f"Missing simplifier configuration in {path.name}: {name}")
        for node in patch.values():
            if isinstance(node, dict) and "opencc_config" in node:
                if not (root / "opencc" / node["opencc_config"]).is_file():
                    raise ValueError(f"Missing OpenCC config in {path.name}: {node}")
    def check_files(node):
        if isinstance(node, dict):
            if "file" in node:
                dictionary = root / "opencc" / node["file"]
                if not dictionary.is_file():
                    source = dictionary.with_suffix(".txt")
                    if not (allow_release_sources and node.get("type") == "ocd2"
                            and source.is_file()):
                        raise ValueError(f"Missing OpenCC dictionary: {node['file']}")
            for value in node.values():
                check_files(value)
        elif isinstance(node, list):
            for value in node:
                check_files(value)
    for path in (root / "opencc").glob("*.json"):
        config = json.loads(read(path))
        if path.stem in {"wanxiang_t2s", "wanxiang_t2hk", "wanxiang_t2tw"}:
            if not isinstance(config.get("segmentation"), dict):
                raise ValueError(f"Missing OpenCC 1.x segmentation: {path.name}")
        check_files(config)


def build(args):
    source, lmdg, root = args.upstream.resolve(), args.lmdg.resolve(), args.output.resolve()
    if root.exists():
        raise ValueError("Output must be a new directory")
    if not (lmdg / "dicts_hant/zi.dict.yaml").is_file():
        raise ValueError("Official dicts_hant is missing")
    root.mkdir(parents=True)
    # 工作流程提供 wanxiang-base；只複製其根目錄下的方案與資料檔。
    for path in source.iterdir():
        if path.name.endswith(".custom.yaml"):
            continue
        if path.is_file() and (path.suffix in {".yaml", ".txt"} or path.name == "LICENSE"):
            shutil.copy2(path, root / path.name)
    # 明確限制可複製的目錄，絕不包含上游的 plum 安裝程式。
    for folder in ("lua", "opencc", "custom"):
        shutil.copytree(source / folder, root / folder)
    for name in ("wanxiang_s2t.json", "wanxiang_s2hk.json", "wanxiang_s2tw.json"):
        (root / "opencc" / name).unlink(missing_ok=True)
    shutil.copytree(lmdg / "dicts_hant", root / "dicts")
    # 優先採用官方繁體詞典；缺少的詞表再由方案轉換產生。
    for path in (source / "dicts").glob("*.dict.yaml"):
        target = root / "dicts" / path.name
        if not target.exists():
            convert_dictionary(path, target)
    convert_dictionary(source / "custom_phrase.dict.yaml", root / "custom_phrase.dict.yaml")
    custom = args.custom
    additions = custom / "overrides/zi.dict.新增部分.yaml"
    if additions.is_file():
        zi = root / "dicts/zi.dict.yaml"
        write(zi, read(zi).rstrip() + "\n" + read(additions).strip() + "\n")
    zi = root / "dicts/zi.dict.yaml"
    write(zi, "\n".join(line for line in read(zi).splitlines() if line.strip()) + "\n")
    fish = root / "dicts/wuzhong.dict.yaml"
    write(fish, read(fish).replace("蝨目魚", "虱目魚"))

    cc = root / "opencc/wanxiang"
    supply_opencc_dictionaries(args.opencc_source, cc)
    variants = cc / "TWVariants.txt"
    changes = custom / "overrides/修改TWVariants.txt"
    if changes.is_file():
        if not variants.is_file():
            subprocess.run(["opencc_dict", "-i", str(variants.with_suffix(".ocd2")),
                            "-o", str(variants), "-f", "ocd2", "-t", "text"], check=True)
        lines = [s.strip() for s in (read(variants) + "\n" + read(changes)).splitlines() if s.strip()]
        counts = Counter(lines)
        write(variants, "\n".join(s for s in lines if counts[s] == 1) + "\n")

    # 從上游詞組配對推導缺少的繁轉簡詞表。
    ts_phrases = cc / "Custom_TSPhrases.txt"
    if not ts_phrases.is_file():
        reverse_phrases = {}
        for line in read(cc / "Custom_STPhrases.txt").splitlines():
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            simplified, traditional_values = line.split("\t", 1)
            for traditional in traditional_values.split():
                values = reverse_phrases.setdefault(traditional, [])
                if simplified not in values:
                    values.append(simplified)
        write(ts_phrases, "\n".join(key + "\t" + " ".join(values)
                                    for key, values in reverse_phrases.items()) + "\n")

    # 解開上游 emoji 詞典以便編輯，稍後再處理其輸出格式。
    emoji = cc / "emoji.txt"
    compiled_emoji = emoji.with_suffix(".ocd2")
    if compiled_emoji.is_file():
        subprocess.run(["opencc_dict", "-i", str(compiled_emoji), "-o", str(emoji),
                        "-f", "ocd2", "-t", "text"], check=True)
    # 上游也可能只提供文字檔；加入使用者自訂別名之前先完成轉換。
    lines = convert(read(emoji), "s2t.json").splitlines()
    emoji_additions = custom / "overrides/emoji新增.txt"
    if emoji_additions.is_file():
        lines.extend(read(emoji_additions).splitlines())
    # 不同的簡體鍵值可能轉換成相同的繁體鍵值。
    mapping = {}
    for line in lines:
        if not line or line.startswith("#"):
            continue
        key, values = line.split("\t", 1)
        bucket = mapping.setdefault(key, [])
        for value in values.split(" "):
            if value and value not in bucket:
                bucket.append(value)
    write(emoji, "\n".join(k + "\t" + " ".join(v) for k, v in mapping.items()) + "\n")
    # 倉庫比照上游原始碼配置，只保留文字檔；Release 打包時才編譯
    # 暫存副本，並改寫該副本內的 JSON 引用。
    prepare_source_opencc(root)
    remove_upstream_st_dictionaries(root)
    # 三個繁轉設定以 custom_configs/opencc 為唯一來源；原樣複製後不再改寫。
    copy_custom_opencc_configs(custom, root)

    for name in ("chinese_english", "english_chinese", "others", "tips_show", "sentence"):
        path = root / "lua/data" / (name + ".txt")
        if path.exists():
            write(path, convert(read(path)))
    for name in ("shijian", "number_conversion"):
        path = root / "lua/wanxiang" / (name + ".lua")
        write(path, convert(read(path)).replace("叄", "參"))
    symbols = root / "wanxiang_symbols.yaml"
    text = read(symbols)
    preserved = {}
    for key in ("/3", "/pp", "/kx"):
        matches = re.findall(r"(?m)^\s*'" + re.escape(key) + r"':[^\n]*", text)
        if len(matches) != 1:
            raise ValueError(f"Symbol entry changed upstream: {key}")
        preserved[key] = matches[0].replace("叁", "參", 1) if key == "/3" else matches[0]
    text = convert(text).replace("叄", "參")
    for key, line in preserved.items():
        text = re.sub(r"(?m)^\s*'" + re.escape(key) + r"':[^\n]*", lambda m: line, text)
    write(symbols, text)

    def revision(path):
        return subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()
    build_info = {"scheme": revision(source), "dicts_hant": revision(lmdg)}
    if emoji_additions.is_file():
        build_info["emoji_additions"] = hashlib.sha256(read(emoji_additions).encode("utf-8")).hexdigest()
    write(root / "build-info.json", json.dumps(build_info, indent=2) + "\n")
    validate(root, allow_release_sources=True)
    if args.gram:
        if not args.gram.is_file() or args.gram.stat().st_size == 0:
            raise ValueError("Traditional language model is missing or empty")
        shutil.copy2(args.gram, root / "wanxiang-lts-zh-hant.gram")
    if args.archives:
        if not args.gram:
            raise ValueError("Both release packages require a validated language model")
        args.archives.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory() as folder:
            release_root = Path(folder) / "hant"
            shutil.copytree(root, release_root)
            prepare_release_opencc(release_root)
            validate(release_root)
            for kind in ("base", "full"):
                with zipfile.ZipFile(args.archives / f"rime-wanxiang-{kind}.zip", "w", zipfile.ZIP_DEFLATED) as archive:
                    for path in sorted(release_root.rglob("*")):
                        if path.is_file() and path.name != "build-info.json" and not (kind == "base" and path.suffix == ".gram"):
                            archive.write(path, path.relative_to(release_root))
    print("Traditional build and dependency checks passed:", root)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in ("upstream", "lmdg", "output", "opencc-source"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--custom", type=Path, default=Path("custom_configs"))
    parser.add_argument("--gram", type=Path)
    parser.add_argument("--archives", type=Path)
    build(parser.parse_args())
