"""Build a standalone Traditional Base scheme from two upstream snapshots."""
import argparse
from collections import Counter
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
    """Preserve Wanxiang tables; fill missing standard dictionaries from OpenCC."""
    for name in ("STCharacters", "STPhrases", "TSCharacters", "TSPhrases", "HKVariants", "TWVariants"):
        text = target / (name + ".txt")
        compiled = target / (name + ".ocd2")
        if text.is_file() or (compiled.is_file() and compiled.stat().st_size > 0):
            continue
        supplied = source / text.name
        if not supplied.is_file():
            raise ValueError(f"Missing OpenCC source: {supplied}")
        shutil.copy2(supplied, text)


def convert_dictionary(source, target):
    # Only text changes: all codes, frequencies and other fields stay byte-for-byte.
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


def validate(root):
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
            if "file" in node and not (root / "opencc" / node["file"]).is_file():
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
    # The workflow supplies wanxiang-base; copy its root scheme/data files only.
    for path in source.iterdir():
        if path.name.endswith(".custom.yaml"):
            continue
        if path.is_file() and (path.suffix in {".yaml", ".txt"} or path.name == "LICENSE"):
            shutil.copy2(path, root / path.name)
    # Explicit directory allowlist: never include upstream's plum installer.
    for folder in ("lua", "opencc", "custom"):
        shutil.copytree(source / folder, root / folder)
    shutil.copytree(lmdg / "dicts_hant", root / "dicts")
    # The official Hant set currently lacks these new 18.x auxiliary dictionaries.
    for name in ("abbrev", "t9_abbrev"):
        target = root / "dicts" / (name + ".dict.yaml")
        if not target.exists():
            convert_dictionary(source / "dicts" / target.name, target)
    convert_dictionary(source / "custom_phrase.dict.yaml", root / "custom_phrase.dict.yaml")
    custom = args.custom
    additions = custom / "zi.dict.新增部分.yaml"
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
    changes = custom / "修改TWVariants.txt"
    if changes.is_file():
        if not variants.is_file():
            subprocess.run(["opencc_dict", "-i", str(variants.with_suffix(".ocd2")),
                            "-o", str(variants), "-f", "ocd2", "-t", "text"], check=True)
        lines = [s.strip() for s in (read(variants) + "\n" + read(changes)).splitlines() if s.strip()]
        counts = Counter(lines)
        write(variants, "\n".join(s for s in lines if counts[s] == 1) + "\n")

    # Use the maintained custom configs verbatim instead of generating JSON.
    for name in ("wanxiang_t2s.json", "wanxiang_t2hk.json", "wanxiang_t2tw.json"):
        shutil.copy2(custom / "opencc" / name, root / "opencc" / name)

    # Decode the upstream emoji dictionary, convert to Traditional, then compile below.
    emoji = cc / "emoji.txt"
    compiled_emoji = emoji.with_suffix(".ocd2")
    if compiled_emoji.is_file():
        subprocess.run(["opencc_dict", "-i", str(compiled_emoji), "-o", str(emoji),
                        "-f", "ocd2", "-t", "text"], check=True)
    # Upstream may ship only text; use it directly in that case.
    lines = convert(read(emoji), "s2t.json").splitlines()
    # Different Simplified keys can become the same Traditional key.
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
    for path in cc.glob("*.txt"):
        if path.name.startswith("Custom_"):
            continue
        # Legacy Lua custom tables used tabs between alternatives; OpenCC uses spaces.
        normalized = []
        for line in read(path).splitlines():
            # Ubuntu's OpenCC 1.1 compiler rejects comments and blank lines.
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            if "\t" in line:
                key, values = line.split("\t", 1)
                line = key + "\t" + values.replace("\t", " ")
            normalized.append(line)
        write(path, "\n".join(normalized) + "\n")
        compiled = path.with_suffix(".ocd2")
        compiled.unlink(missing_ok=True)
        subprocess.run(["opencc_dict", "-i", str(path), "-o", str(compiled),
                        "-f", "text", "-t", "ocd2"], check=True)
        # Some versions report dictionary errors while returning exit status 0.
        if not compiled.is_file() or compiled.stat().st_size == 0:
            raise ValueError(f"OpenCC did not compile dictionary: {path}")

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
    write(root / "build-info.json", json.dumps({"scheme": revision(source), "dicts_hant": revision(lmdg)}, indent=2) + "\n")
    validate(root)
    if args.gram:
        if not args.gram.is_file() or args.gram.stat().st_size == 0:
            raise ValueError("Traditional language model is missing or empty")
        shutil.copy2(args.gram, root / "wanxiang-lts-zh-hant.gram")
    if args.archives:
        if not args.gram:
            raise ValueError("Both release packages require a validated language model")
        args.archives.mkdir(parents=True, exist_ok=True)
        for kind in ("base", "full"):
            with zipfile.ZipFile(args.archives / f"rime-wanxiang-{kind}.zip", "w", zipfile.ZIP_DEFLATED) as archive:
                for path in sorted(root.rglob("*")):
                    if path.is_file() and not (kind == "base" and path.suffix == ".gram"):
                        archive.write(path, path.relative_to(root))
    print("Traditional build and dependency checks passed:", root)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in ("upstream", "lmdg", "output", "opencc-source"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--custom", type=Path, default=Path("custom_configs"))
    parser.add_argument("--gram", type=Path)
    parser.add_argument("--archives", type=Path)
    build(parser.parse_args())
