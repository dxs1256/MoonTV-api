#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""视频源健康检测脚本。

用法:
    python check.py                 # 使用默认关键词
    python check.py "我的关键词"     # 自定义搜索关键词

检测逻辑:
    - 健康检测: 请求 ?ac=videolist，校验返回 JSON 含 list 数组（而非只看 HTTP 200）
    - 搜索检测: 请求 ?ac=videolist&wd=关键词，校验结果并匹配 vod_name
    - 带浏览器 UA、超时、重试、并发控制

输出:
    report.md   —— 当前状态表 + 最近7天趋势 + 30天历史数据(JSON)
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SOURCES_PATH = os.path.join(BASE_DIR, "sources.json")
REPORT_PATH = os.path.join(BASE_DIR, "report.md")

MAX_DAYS = 30
WARN_STREAK = 3
SEARCH_KEYWORD = sys.argv[1] if len(sys.argv) > 1 else "斗罗大陆"
TIMEOUT_MS = 10000
CONCURRENT_LIMIT = 10
MAX_RETRY = 3
RETRY_DELAY_MS = 500

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

STATUS_ORDER = {"🚨": 1, "❌": 2, "⚠️": 3, "✅": 4, "🚫": 5}


def http_get_json(url):
    """带浏览器 UA 的 GET 请求，返回解析后的 JSON；失败返回 None。"""
    for attempt in range(1, MAX_RETRY + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=TIMEOUT_MS / 1000) as resp:
                if resp.status != 200:
                    return None
                return json.loads(resp.read().decode("utf-8", "ignore"))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError,
                ValueError, OSError):
            if attempt < MAX_RETRY:
                time.sleep(RETRY_DELAY_MS / 1000)
    return None


def health_check(api):
    """健康检测：请求 ?ac=videolist，校验返回 JSON 含 list 数组。"""
    data = http_get_json(api + "?ac=videolist")
    return isinstance(data, dict) and isinstance(data.get("list"), list)


def match_keyword(item, keyword):
    """判断单个结果是否命中关键词。"""
    if isinstance(item, str):
        return keyword in item
    if isinstance(item, dict):
        for field in ("vod_name", "name", "title"):
            if keyword in str(item.get(field, "")):
                return True
        return keyword in json.dumps(item, ensure_ascii=False)
    return False


def search_test(api, keyword):
    """搜索检测：请求 ?ac=videolist&wd=，校验结果并判断命中。"""
    url = api + "?ac=videolist&wd=" + urllib.parse.quote(keyword)
    data = http_get_json(url)
    if not isinstance(data, dict) or not isinstance(data.get("list"), list):
        return "❌"
    items = data["list"]
    if not items:
        return "无结果"
    return "✅" if any(match_keyword(item, keyword) for item in items) else "不匹配"


def load_sources():
    with open(SOURCES_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    return [
        {
            "name": s.get("name", k),
            "api": s.get("api", ""),
            "detail": s.get("detail", "-"),
            "disabled": bool(s.get("disabled", False)),
            "adult": bool(s.get("adult", False)),
        }
        for k, s in cfg.get("api_site", {}).items()
    ]


def load_history():
    """从 report.md 中提取历史检测数据(JSON)。"""
    if not os.path.exists(REPORT_PATH):
        return []
    with open(REPORT_PATH, "r", encoding="utf-8") as f:
        old = f.read()
    match = old.split("```json\n", 1)
    if len(match) < 2:
        return []
    try:
        return json.loads(match[1].split("\n```", 1)[0])
    except (ValueError, IndexError):
        return []


def run_checks(sources, keyword):
    """并发执行全部源的健康 + 搜索检测。"""
    def task(src):
        if src["disabled"]:
            return {**src, "success": False, "searchStatus": "无法搜索"}
        ok = health_check(src["api"])
        search = search_test(src["api"], keyword)
        return {**src, "success": ok, "searchStatus": search}

    results = {}
    with ThreadPoolExecutor(max_workers=CONCURRENT_LIMIT) as pool:
        futures = {pool.submit(task, s): s["api"] for s in sources}
        for fut in as_completed(futures):
            api = futures[fut]
            try:
                results[api] = fut.result()
            except Exception as exc:
                results[api] = {"api": api, "success": False, "searchStatus": str(exc)}
    return results


def compute_stats(sources, history, today_results):
    """汇总状态、成功率、趋势与最终状态标记。"""
    stats = {}
    for src in sources:
        api = src["api"]
        st = {
            "name": src["name"], "api": api, "detail": src["detail"],
            "disabled": src["disabled"], "ok": 0, "fail": 0, "trend": "",
            "searchStatus": "-", "status": "❌",
        }

        if not src["disabled"]:
            for day in history:
                row = next((x for x in day.get("results", []) if x.get("api") == api), None)
                if row is None:
                    continue
                if row.get("success"):
                    st["ok"] += 1
                else:
                    st["fail"] += 1

            streak = 0
            for day in reversed(history):
                row = next((x for x in day.get("results", []) if x.get("api") == api), None)
                if row is None:
                    break
                if row.get("success"):
                    break
                streak += 1

            total = st["ok"] + st["fail"]
            st["successRate"] = f"{st['ok'] / total * 100:.1f}%" if total else "-"

            recent = history[-7:]
            st["trend"] = "".join(
                "✅" if next((x for x in d.get("results", []) if x.get("api") == api), {}).get("success")
                else "❌"
                for d in recent
            )
        else:
            st["successRate"] = "-"
            st["trend"] = "🚫" * min(len(history[-7:]), 7)

        latest = today_results.get(api)
        if latest:
            st["searchStatus"] = latest["searchStatus"]

        if src["disabled"]:
            st["status"] = "🚫"
        elif streak >= WARN_STREAK:
            st["status"] = "🚨"
        elif not latest or not latest["success"]:
            st["status"] = "❌"
        elif latest["searchStatus"] == "✅":
            st["status"] = "✅"
        else:
            st["status"] = "⚠️"

        stats[api] = st
    return stats


def write_report(sources, history, today_record, stats, keyword, now_str):
    """生成 report.md。"""
    lines = [
        "# 源接口健康检测报告",
        "",
        f"最近更新时间：{now_str}",
        "",
        f"**总源数:** {len(sources)} | **检测关键词:** {keyword}",
        "",
        "| 状态 | 资源名称 | 地址 | API | 搜索功能 | 成功次数 | 失败次数 | 成功率 | 最近7天趋势 |",
        "|------|---------|-----|-----|---------|---------:|--------:|-------:|--------------|",
    ]
    for s in sorted(stats.values(), key=lambda x: STATUS_ORDER.get(x["status"], 9)):
        detail = f"[Link]({s['detail']})" if s["detail"].startswith("http") else s["detail"]
        api = f"[Link]({s['api']})"
        lines.append(
            f"| {s['status']} | {s['name']} | {detail} | {api} | {s['searchStatus']} "
            f"| {s['ok']} | {s['fail']} | {s['successRate']} | {s['trend']} |"
        )
    lines += [
        "",
        "<details>",
        "<summary>📜 点击展开查看历史检测数据 (JSON)</summary>",
        "",
        "```json",
        json.dumps(history, ensure_ascii=False, indent=2),
        "```",
        "</details>",
        "",
    ]
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main():
    sources = load_sources()
    print(f"⏳ 正在检测 {len(sources)} 个源（关键词: {SEARCH_KEYWORD}）...")

    today_results = run_checks(sources, SEARCH_KEYWORD)

    history = load_history()
    today_record = {
        "date": time.strftime("%Y-%m-%d"),
        "keyword": SEARCH_KEYWORD,
        "results": [
            {
                "api": r["api"], "name": r["name"], "success": r["success"],
                "searchStatus": r.get("searchStatus", "-"),
            }
            for r in today_results.values()
        ],
    }
    history.append(today_record)
    if len(history) > MAX_DAYS:
        history = history[-MAX_DAYS:]

    stats = compute_stats(sources, history, today_results)

    now_str = (time.strftime("%Y-%m-%d %H:%M") + " CST")
    write_report(sources, history, today_record, stats, SEARCH_KEYWORD, now_str)

    ok = sum(1 for s in stats.values() if s["status"] == "✅")
    warn = sum(1 for s in stats.values() if s["status"] == "⚠️")
    bad = sum(1 for s in stats.values() if s["status"] in ("❌", "🚨"))
    print(f"📄 报告已生成: {REPORT_PATH}")
    print(f"📊 统计: ✅ {ok} | ⚠️ {warn} | ❌/🚨 {bad}")


if __name__ == "__main__":
    main()
