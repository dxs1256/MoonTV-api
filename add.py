#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""安全地向 sources.json 添加新源，自动校验格式并生成唯一 key。

用法:
    # 交互模式（推荐，按提示填写）
    python add.py

    # 命令行模式
    python add.py --name "源名称" --api "https://example.com/api.php/provide/vod" --detail "https://example.com"

    # api 已存在时强制添加
    python add.py --name "源名称" --api "..." --force

说明:
    - 自动校验 name / api / detail 格式
    - api 重复时默认拒绝，避免引入重复源
    - 自动根据站点域名生成唯一 key，无需手写
    - 写回时保持固定缩进，不会破坏 JSON 结构
"""
import argparse
import json
import os
import re
import sys
import urllib.parse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SOURCES_PATH = os.environ.get("SOURCES_PATH") or os.path.join(BASE_DIR, "sources.json")
SITES_KEY = "api_site"


def normalize_api(url):
    return str(url or "").strip().rstrip("/")


def is_http_url(url):
    try:
        parsed = urllib.parse.urlparse(url)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except ValueError:
        return False


def make_key(api, detail, existing):
    """根据 detail 或 api 的域名生成唯一 key。"""
    base = ""
    for url in (detail, api):
        if url and is_http_url(url):
            host = urllib.parse.urlparse(url).netloc.split("@")[-1]
            host = host.split(":")[0]
            base = re.sub(r"[^a-z0-9]", "", host.lower())
            if base:
                break
    if not base:
        base = "source"
    key = base
    n = 2
    while key in existing:
        key = f"{base}{n}"
        n += 1
    return key


def prompt(label, required=True, default=None):
    while True:
        suffix = f" [{default}]" if default else ""
        try:
            value = input(f"{label}{suffix}: ").strip()
        except EOFError:
            print("\n输入结束，操作已取消")
            sys.exit(1)
        if not value and default is not None:
            value = default
        if value or not required:
            return value
        print("  该字段不能为空，请重新输入")


def collect_interactive(api_site):
    print("=== 添加新源（直接回车使用默认值 / 跳过可选项）===")
    name = prompt("资源名称")
    while True:
        api = prompt("API 地址（http/https）")
        if is_http_url(api):
            break
        print("  必须是合法的 http/https 地址，请重新输入")
    detail = prompt("站点主页（可选，回车跳过）", required=False)

    norm = normalize_api(api)
    for key, src in api_site.items():
        if normalize_api(src.get("api")) == norm:
            print(f"⚠️ 该 api 已存在（key: {key}, 名称: {src.get('name')}），未重复添加")
            return None
    return name, api, detail or "-"


def main():
    parser = argparse.ArgumentParser(description="向 sources.json 添加新源")
    parser.add_argument("--name", help="资源名称")
    parser.add_argument("--api", help="API 地址（provide/vod 接口）")
    parser.add_argument("--detail", help="站点主页，可选")
    parser.add_argument("--force", action="store_true", help="api 已存在时仍强制添加")
    args = parser.parse_args()

    with open(SOURCES_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    api_site = cfg.get(SITES_KEY, {})

    if args.name or args.api:
        if not args.name or not args.api:
            parser.error("命令行模式必须同时提供 --name 和 --api")
        name, api, detail = args.name.strip(), args.api.strip(), (args.detail or "-").strip()
        if not name:
            parser.error("--name 不能为空")
        if not is_http_url(api):
            parser.error("--api 必须是合法的 http/https 地址")
        if detail != "-" and not is_http_url(detail):
            parser.error("--detail 必须是合法的 http/https 地址")
        norm = normalize_api(api)
        for key, src in api_site.items():
            if normalize_api(src.get("api")) == norm:
                if not args.force:
                    print(f"❌ api 已存在（key: {key}, 名称: {src.get('name')}），未添加")
                    print("   如确认要重复添加，请加 --force")
                    return
        entry = (name, api, detail)
    else:
        entry = collect_interactive(api_site)
        if entry is None:
            return

    name, api, detail = entry
    key = make_key(api, detail, api_site)
    api_site[key] = {"name": name, "api": api, "detail": detail}
    cfg[SITES_KEY] = api_site

    with open(SOURCES_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"\n✅ 已添加 [{key}] {name}")
    print(f"   api: {api}")
    print(f"   当前共 {len(api_site)} 个源")
    print("\n下一步：python check.py 检测，或提交后等待 Actions 定时运行")


if __name__ == "__main__":
    main()
