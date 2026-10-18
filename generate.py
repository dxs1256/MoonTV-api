#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从主数据源 sources.json 生成分发版本。

用法:
    python generate.py

生成:
    dist/full.json     全部源（保留 adult / disabled 标记）
    dist/full.txt      上面 full.json 的 Base58 订阅编码
    dist/clean.json    精简版（剔除 adult 与 disabled 源）
    dist/clean.txt     上面 clean.json 的 Base58 订阅编码
    dist/healthy.json  健康版（在 clean 基础上，只保留最近一次检测通过的源）
    dist/healthy.txt   上面 healthy.json 的 Base58 订阅编码

healthy 版本依赖 report.md 中的最近一次检测结果：
    - 先运行 python check.py 生成报告，再运行本脚本，healthy 才是最新的
    - 若 report.md 不存在（或还没有检测数据），自动跳过 healthy 版本

每次修改 sources.json 后运行本脚本即可同步所有分发版本。
"""
import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SOURCES_PATH = os.path.join(BASE_DIR, "sources.json")
REPORT_PATH = os.path.join(BASE_DIR, "report.md")
DIST_DIR = os.path.join(BASE_DIR, "dist")

CACHE_TIME_KEY = "cache_time"
SITES_KEY = "api_site"

# True: healthy 版本要求搜索也命中（searchStatus == "✅"）
# False: 只要健康检测通过（API 可用）即可
REQUIRE_SEARCH_PASS = False

B58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def load_sources():
    with open(SOURCES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_latest_results():
    """读取 report.md 中最近一次检测结果，返回 {api: 结果}；无数据返回 None。"""
    if not os.path.exists(REPORT_PATH):
        return None
    with open(REPORT_PATH, "r", encoding="utf-8") as f:
        text = f.read()
    marker = "```json\n"
    if marker not in text:
        return None
    try:
        history = json.loads(text.split(marker, 1)[1].split("\n```", 1)[0])
    except (ValueError, IndexError):
        return None
    if not history:
        return None
    latest = history[-1].get("results", [])
    return {r["api"]: r for r in latest if "api" in r}


def build_config(cache_time, api_site):
    return {CACHE_TIME_KEY: cache_time, SITES_KEY: api_site}


def base58_encode(data):
    """Bitcoin 字母表 Base58 编码，输出与 bs58.encode 一致。"""
    n = int.from_bytes(data, "big")
    encoded = ""
    while n > 0:
        n, rem = divmod(n, 58)
        encoded = B58_ALPHABET[rem] + encoded
    leading_zeros = len(data) - len(data.lstrip(b"\x00"))
    return "1" * leading_zeros + encoded


def write_variant(name, config):
    """写出 JSON 文件及对应的 Base58 订阅文件。"""
    raw = json.dumps(config, ensure_ascii=False, indent=2).encode("utf-8")
    with open(os.path.join(DIST_DIR, f"{name}.json"), "wb") as f:
        f.write(raw)
    with open(os.path.join(DIST_DIR, f"{name}.txt"), "w", encoding="utf-8") as f:
        f.write(base58_encode(raw))


def is_publishable(src):
    return not src.get("disabled") and not src.get("adult")


def build_healthy_site(clean_site, latest):
    """在 clean 基础上，只保留最近一次检测通过的源。"""
    healthy = {}
    for key, src in clean_site.items():
        result = latest.get(src.get("api"))
        if not result or not result.get("success"):
            continue
        if REQUIRE_SEARCH_PASS and result.get("searchStatus") != "✅":
            continue
        healthy[key] = src
    return healthy


def main():
    os.makedirs(DIST_DIR, exist_ok=True)
    cfg = load_sources()
    cache_time = cfg.get(CACHE_TIME_KEY, 3600)
    api_site = cfg.get(SITES_KEY, {})

    full = build_config(cache_time, api_site)
    clean_site = {k: v for k, v in api_site.items() if is_publishable(v)}
    clean = build_config(cache_time, clean_site)

    write_variant("full", full)
    write_variant("clean", clean)

    adult_count = sum(1 for v in api_site.values() if v.get("adult"))
    disabled_count = sum(1 for v in api_site.values() if v.get("disabled"))
    print(f"✅ 主数据源共 {len(api_site)} 个源")
    print(f"   - dist/full.json / full.txt    全部源（含 adult×{adult_count}、disabled×{disabled_count}）")
    print(f"   - dist/clean.json / clean.txt  精简版 {len(clean_site)} 个源（已剔除 adult 与 disabled）")

    latest = load_latest_results()
    if latest is None:
        print("⚠️ 未找到检测报告，跳过 healthy 版本（先运行 python check.py）")
        return

    healthy_site = build_healthy_site(clean_site, latest)
    write_variant("healthy", build_config(cache_time, healthy_site))
    dropped = len(clean_site) - len(healthy_site)
    print(f"   - dist/healthy.json / healthy.txt 健康版 {len(healthy_site)} 个源（剔除检测失败 {dropped} 个）")


if __name__ == "__main__":
    main()
