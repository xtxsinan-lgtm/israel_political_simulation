"""模块规格自动检查（阶段2）。

检查项：
  1. 模板章节 0–13 是否齐全
  2. 第11节验收测试表行数（≥8）
  3. 含糊词出现次数
  4. 规格中引用的 snake_case 参数ID 是否存在于 registry 或任一规格的附录A提案中
  5. 汇总所有附录A新增参数提案与附录B接口变更提案

用法: .venv/bin/python tools/check_specs.py [--verbose]
"""
import os
import re
import sys

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPEC_DIR = os.path.join(ROOT, "docs", "specs")
REGISTRY = os.path.join(ROOT, "docs", "registry", "parameters.yaml")

VAGUE = ["适当", "若干", "视情况", "酌情", "一定程度", "相应地调整", "合理的", "等等"]
SECTION_RE = re.compile(r"^##\s*(\d{1,2})[\.．、\s]", re.M)
ID_IN_TICKS = re.compile(r"`([a-z][a-z0-9_]{3,})(?:\[[^\]`]*\])?`")
TARGET_RE = re.compile(r"target:\s*([a-z][a-z0-9_]+)")
SPECIAL_TARGETS = {"custom", "flag", "modifier", "event", "float", "int", "str", "string", "bool"}


def load_registry_ids():
    data = yaml.safe_load(open(REGISTRY, encoding="utf-8"))
    ids = {p["id"] for p in data["parameters"]}
    ents = set()
    for v in data.get("entities", {}).values():
        ents.update(v)
    return ids, ents


def appendix(text, letter):
    m = re.search(r"^#+\s*附录%s[^\n]*\n(.*?)(?=^#+\s*附录[A-Z]|\Z)" % letter, text, re.M | re.S)
    return m.group(1) if m else ""


def proposed_ids(text):
    block = appendix(text, "A")
    ids = set(re.findall(r"\bid:\s*([a-z][a-z0-9_]+)", block))
    ids.update(re.findall(r"^  ([a-z][a-z0-9_]+):\s*$", block, re.M))
    return ids


def proposed_entities(text):
    block = appendix(text, "A")
    ents = set()
    for m in re.findall(r"\[([a-z0-9_,\s]+)\]", block):
        for item in m.split(","):
            tok = item.strip()
            if re.match(r"^[a-z][a-z0-9_]+$", tok):
                ents.add(tok)
    return ents


def acceptance_rows(text):
    m = re.search(r"^##\s*11[\.．、\s][^\n]*\n(.*?)(?=^##\s*12[\.．、\s]|\Z)", text, re.M | re.S)
    if not m:
        return 0
    rows = [l for l in m.group(1).splitlines() if l.strip().startswith("|")]
    rows = [r for r in rows if not re.match(r"^\|\s*-", r.strip())]
    return max(0, len(rows) - 1)  # 去掉表头


def main():
    verbose = "--verbose" in sys.argv
    reg_ids, ents = load_registry_ids()
    specs = sorted(f for f in os.listdir(SPEC_DIR) if re.match(r"M\d\d_.*\.md$", f)) if os.path.isdir(SPEC_DIR) else []
    texts = {f: open(os.path.join(SPEC_DIR, f), encoding="utf-8").read() for f in specs}
    all_proposed = {}
    for f, t in texts.items():
        for pid in proposed_ids(t):
            all_proposed.setdefault(pid, []).append(f[:3])
        ents.update(proposed_entities(t))
    known = reg_ids | set(all_proposed) | ents | SPECIAL_TARGETS
    ok_all = True
    print("规格 %d 份；registry 参数 %d 个；附录A提案 %d 个" % (len(specs), len(reg_ids), len(all_proposed)))
    for f, t in texts.items():
        secs = {int(s) for s in SECTION_RE.findall(t)}
        missing = [i for i in range(0, 14) if i not in secs]
        tests = acceptance_rows(t)
        vague = {w: t.count(w) for w in VAGUE if t.count(w)}
        refs = set(TARGET_RE.findall(t))
        unknown_targets = sorted(r for r in refs if r not in known)
        status = "OK"
        if missing or tests < 8 or unknown_targets:
            status = "需修改"
            ok_all = False
        print("\n[%s] %s  行数=%d  验收测试=%d" % (status, f, t.count("\n"), tests))
        if missing:
            print("  缺少章节:", missing)
        if vague:
            print("  含糊词:", vague)
        if unknown_targets:
            print("  效果 target 引用了未登记参数:", unknown_targets)
        if verbose:
            ticks = sorted({m for m in ID_IN_TICKS.findall(t) if m not in known and m not in ents})
            if ticks:
                print("  反引号中未登记的标识符（可能是字段名，人工确认）:", ticks[:40])
        b = appendix(t, "B").strip()
        if b:
            print("  附录B接口变更提案: 有（%d 字）" % len(b))
    dup = {k: v for k, v in all_proposed.items() if len(v) > 1}
    if dup:
        print("\n多个规格提出了同名参数（需合并）:")
        for k, v in sorted(dup.items()):
            print("  %s: %s" % (k, ", ".join(v)))
    sys.exit(0 if ok_all else 1)


if __name__ == "__main__":
    main()
