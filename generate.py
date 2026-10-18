#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 sources.json 生成健康版订阅。

用法:
    python check.py      # 先检测，生成 report.md
    python generate.py   # 再生成 dist/healthy.json 与 dist/healthy.txt

说明:
    sources.json 本身即完整订阅配置，可直接作为 JSON 订阅地址使用。
    healthy 版读取 report.md 最近一次检测结果，只保留检测通过的源。
    检测失败的源自动从 healthy 订阅中消失，恢复后自动回来。
    sources.json 始终保留全部源，不因检测失败而删除。
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
    """读取 report.md 中最近一次检测结果，返回 {key: 结果}；无数据返回 None。"""
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
    results = {}
    for row in latest:
        if "api" not in row:
            continue
        results[row.get("key") or row["api"]] = row
    return results


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


def main():
    cfg = load_sources()
    cache_time = cfg.get(CACHE_TIME_KEY, 3600)
    api_site = cfg.get(SITES_KEY, {})

    latest = load_latest_results()
    if latest is None:
        print("⚠️ 未找到检测报告，跳过 healthy 生成（请先运行 python check.py）")
        return

    healthy = {}
    for key, src in api_site.items():
        result = latest.get(key) or latest.get(src.get("api"))
        if not result or not result.get("success"):
            continue
        if REQUIRE_SEARCH_PASS and result.get("searchStatus") != "✅":
            continue
        healthy[key] = src

    os.makedirs(DIST_DIR, exist_ok=True)
    write_variant("healthy", {CACHE_TIME_KEY: cache_time, SITES_KEY: healthy})

    dropped = len(api_site) - len(healthy)
    print(f"✅ sources.json 共 {len(api_site)} 个源")
    print(f"   - dist/healthy.json / healthy.txt  健康版 {len(healthy)} 个源（剔除检测失败 {dropped} 个）")


if __name__ == "__main__":
    main()
