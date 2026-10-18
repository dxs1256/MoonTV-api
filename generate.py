#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从主数据源 sources.json 生成分发版本。

用法:
    python generate.py

生成:
    dist/full.json   全部源（保留 adult / disabled 标记）
    dist/clean.json  精简版（剔除 adult 与 disabled 源）

每次修改 sources.json 后运行本脚本即可同步所有分发版本。
"""
import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SOURCES_PATH = os.path.join(BASE_DIR, "sources.json")
DIST_DIR = os.path.join(BASE_DIR, "dist")

CACHE_TIME_KEY = "cache_time"
SITES_KEY = "api_site"


def load_sources():
    with open(SOURCES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def build_config(cache_time, api_site):
    return {CACHE_TIME_KEY: cache_time, SITES_KEY: api_site}


def main():
    os.makedirs(DIST_DIR, exist_ok=True)
    cfg = load_sources()
    cache_time = cfg.get(CACHE_TIME_KEY, 3600)
    api_site = cfg.get(SITES_KEY, {})

    full = build_config(cache_time, api_site)
    clean_site = {
        k: v for k, v in api_site.items()
        if not v.get("disabled") and not v.get("adult")
    }
    clean = build_config(cache_time, clean_site)

    full_path = os.path.join(DIST_DIR, "full.json")
    clean_path = os.path.join(DIST_DIR, "clean.json")
    with open(full_path, "w", encoding="utf-8") as f:
        json.dump(full, f, ensure_ascii=False, indent=2)
    with open(clean_path, "w", encoding="utf-8") as f:
        json.dump(clean, f, ensure_ascii=False, indent=2)

    adult_count = sum(1 for v in api_site.values() if v.get("adult"))
    disabled_count = sum(1 for v in api_site.values() if v.get("disabled"))
    print(f"✅ 主数据源共 {len(api_site)} 个源")
    print(f"   - dist/full.json  全部源（含 adult×{adult_count}、disabled×{disabled_count}）")
    print(f"   - dist/clean.json  精简版 {len(clean_site)} 个源（已剔除 adult 与 disabled）")


if __name__ == "__main__":
    main()
