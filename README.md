# API 健康检测

视频源（macOS `provide/vod` 接口）可用性检测仓库。定时检测每个源是否正常、搜索是否命中，并自动维护精简版订阅配置。

## 特点

- **单主数据源**：所有源只维护在 `sources.json` 一个文件，`generate.py` 自动生成分发版本，不再多文件同步
- **准确检测**：健康检测校验返回 JSON 的 `list` 字段（而非只看 HTTP 200），并带浏览器 UA、超时、重试、并发控制
- **状态细化**：健康通过但搜索异常标记 ⚠️，连续失败 3 天标记 🚨，检测更可信
- **自动运行**：GitHub Actions 每天定时检测并更新报告

## 目录结构

```
├── sources.json              # 唯一主数据源（在此添加/修改源）
├── generate.py               # 从主数据源生成分发版本
├── check.py                  # 健康+搜索检测脚本，生成 report.md
├── report.md                 # 检测报告（含30天历史）
├── dist/
│   ├── full.json             # 全部源
│   ├── full.txt              # full.json 的 Base58 订阅编码
│   ├── clean.json           # 精简版（剔除 adult / disabled）
│   └── clean.txt             # clean.json 的 Base58 订阅编码
└── .github/workflows/
    └── check.yml             # 定时检测工作流
```

## 添加新源

1. 编辑 `sources.json` 的 `api_site`，按下面格式添加一项：

```json
"新源key": {
  "name": "源名称",
  "api": "https://example.com/api.php/provide/vod",
  "detail": "https://example.com",
  "adult": false,
  "disabled": false
}
```

字段说明：

| 字段 | 必填 | 说明 |
|------|------|------|
| `name` | 是 | 显示名称 |
| `api` | 是 | `provide/vod` 接口地址 |
| `detail` | 否 | 站点主页，用于报告中生成链接 |
| `adult` | 否 | `true` 时不会进入 clean 精简版 |
| `disabled` | 否 | `true` 时跳过检测并标记 🚫 |

2. 运行 `python generate.py` 同步分发版本
3. 运行 `python check.py "关键词"` 本地检测
4. 推送代码，GitHub Actions 会自动完成后续每日检测

## 本地用法

```bash
# 默认关键词检测
python check.py

# 指定关键词
python check.py "斗罗大陆"

# 重新生成分发版本（JSON + Base58 订阅）
python generate.py
```

## 订阅使用

`generate.py` 会同时生成 JSON 和 Base58 订阅文件，播放器订阅时使用 `.txt`：

```
https://raw.githubusercontent.com/<user>/<repo>/main/dist/full.txt
https://raw.githubusercontent.com/<user>/<repo>/main/dist/clean.txt
```

- `full.txt`：全部源
- `clean.txt`：剔除 adult 与 disabled 源后的精简版

需要 JSON 原始配置时用 `dist/full.json` / `dist/clean.json`。Base58 编码与 `bs58` 完全一致。

## 状态说明

| 状态 | 含义 |
|------|------|
| ✅ | 健康检测通过，搜索命中 |
| ⚠️ | 健康检测通过，但搜索无结果/不匹配 |
| ❌ | 健康检测失败 |
| 🚨 | 连续 3 天检测失败 |
| 🚫 | 已禁用，跳过检测 |
