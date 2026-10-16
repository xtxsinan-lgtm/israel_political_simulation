"""从事件库 Markdown 中抽取旗标与修正器，生成登记表并报告孤立项。

用法: .venv/bin/python tools/extract_flags.py
输出: docs/registry/flags.yaml, docs/registry/modifiers.yaml, 以及标准输出的孤立项报告
"""
import os
import re
from collections import defaultdict

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVENT_DIR = os.path.join(ROOT, "docs", "events")
REG_DIR = os.path.join(ROOT, "docs", "registry")

HEAD_RE = re.compile(r"^### ((?:E|R)-[0-9A-Z]+(?:-[0-9]+[a-z]?)?)")
FLAG_RE = re.compile(r"旗标[：:]\s*([^；;，,。（()）\s|*]+)")
MOD_RE = re.compile(r"修正器「([^」]+)」")

# 位于“触发”子块中的行视为读取，其余视为设置
TRIGGER_KEYS = ("**触发**", "**窗口**", "**前置**", "**条件**", "**概率**", "**失效**", "**未触发**", "**前提**")


def scan():
    flags = defaultdict(lambda: {"set_by": set(), "read_by": set()})
    mods = defaultdict(lambda: {"set_by": set(), "read_by": set()})
    for fn in sorted(os.listdir(EVENT_DIR)):
        if not re.match(r"0\d_.*\.md$", fn):
            continue
        current = None
        in_trigger = False
        for line in open(os.path.join(EVENT_DIR, fn), encoding="utf-8"):
            m = HEAD_RE.match(line)
            if m:
                current = m.group(1)
                in_trigger = False
                continue
            if current is None:
                continue
            stripped = line.strip()
            if stripped.startswith("- **"):
                in_trigger = any(k in stripped for k in TRIGGER_KEYS)
            if line.startswith("  - **") and any(k in line for k in TRIGGER_KEYS):
                in_trigger = True
            role = "read_by" if in_trigger else "set_by"
            for f in FLAG_RE.findall(line):
                flags[f][role].add(current)
            for md in MOD_RE.findall(line):
                mods[md][role].add(current)
    return flags, mods


def dump(table, path, kind):
    out = []
    for name in sorted(table):
        entry = table[name]
        out.append({
            "name": name,
            "set_by": sorted(entry["set_by"]),
            "read_by": sorted(entry["read_by"]),
        })
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("# 自动生成：tools/extract_flags.py。不要手工编辑；英文ID在结构化转换时分配。\n")
        yaml.safe_dump({kind: out}, fh, allow_unicode=True, sort_keys=False, width=200)
    return out


def main():
    flags, mods = scan()
    f_out = dump(flags, os.path.join(REG_DIR, "flags.yaml"), "flags")
    m_out = dump(mods, os.path.join(REG_DIR, "modifiers.yaml"), "modifiers")
    never_set = [e["name"] for e in f_out if not e["set_by"]]
    never_read = [e["name"] for e in f_out if not e["read_by"]]
    print("旗标 %d 个，修正器 %d 个" % (len(f_out), len(m_out)))
    print("只被读取、从未被设置的旗标 %d 个（需要上游设置者）" % len(never_set))
    print("只被设置、从未被读取的旗标 %d 个（可能是死旗标或供系统使用）" % len(never_read))


if __name__ == "__main__":
    main()
