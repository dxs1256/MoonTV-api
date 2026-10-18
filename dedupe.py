#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检测并清理 sources.json 中重复的 api 地址。

重复判定：api 去掉首尾空白和末尾斜杠后完全相同。
每组重复只保留第一个出现的源，其余删除。

用法:
    python dedupe.py           # 只检测，不修改文件
    python dedupe.py --apply   # 去重并写回 sources.json
"""
import json
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SOURCES_PATH = os.environ.get("SOURCES_PATH") or os.path.join(BASE_DIR, "sources.json")
SITES_KEY = "api_site"


def normalize_api(url):
    """用于比较的规范化：去首尾空白、去末尾斜杠。"""
    return str(url or "").strip().rstrip("/")


def find_duplicates(api_site):
    """返回 [(重复key, 第一次出现的key), ...]，按文件顺序。"""
    first_seen = {}
    dups = []
    for key, src in api_site.items():
        norm = normalize_api(src.get("api"))
        if not norm:
            continue
        if norm in first_seen:
            dups.append((key, first_seen[norm]))
        else:
            first_seen[norm] = key
    return dups


def main():
    apply = "--apply" in sys.argv[1:]
    with open(SOURCES_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    api_site = cfg.get(SITES_KEY, {})

    dups = find_duplicates(api_site)
    if not dups:
        print(f"✅ 未发现重复 api（共 {len(api_site)} 个源）")
        return

    print(f"发现 {len(dups)} 个重复 api（共 {len(api_site)} 个源）：")
    for key, first in dups:
        print(f"  - [{key}] {api_site[key].get('name', '')}")
        print(f"      与 [{first}] {api_site[first].get('name', '')} 的 api 相同")
        print(f"      {api_site[key].get('api', '')}")

    if not apply:
        print("\n当前为检测模式，未修改文件。执行去重请运行：python dedupe.py --apply")
        return

    dup_keys = {key for key, _ in dups}
    cleaned = {k: v for k, v in api_site.items() if k not in dup_keys}
    cfg[SITES_KEY] = cleaned
    with open(SOURCES_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"\n✅ 已删除 {len(dup_keys)} 个重复项，剩余 {len(cleaned)} 个源")


if __name__ == "__main__":
    main()
