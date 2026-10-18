# API 健康检测

视频源（macOS `provide/vod` 接口）可用性检测仓库。定时检测每个源是否正常、搜索是否命中，并自动生成一份只含健康源的订阅配置。

## 特点

- **单主数据源**：所有源只维护在 `sources.json`，它本身就是完整配置，可直接作为订阅使用
- **健康版订阅**：自动剔除检测失败的源，坏源消失、恢复后自动回来，不用手动维护
- **准确检测**：健康检测校验返回 JSON 的 `list` 字段（而非只看 HTTP 200），带浏览器 UA、超时、重试、并发控制
- **状态细化**：健康通过但搜索异常标记 ⚠️，连续失败 3 天标记 🚨
- **自动运行**：GitHub Actions 每天定时检测并更新报告与健康版订阅

## 目录结构

```
├── sources.json              # 唯一主数据源，也是完整订阅配置
├── check.py                  # 健康+搜索检测，生成 report.md
├── generate.py               # 从检测结果生成健康版订阅
├── report.md                 # 检测报告（含30天历史）
├── dist/
│   ├── healthy.json          # 健康版（只含检测通过的源）
│   └── healthy.txt           # healthy.json 的 Base58 订阅编码
└── .github/workflows/
    └── check.yml             # 定时检测工作流
```

## 添加新源

编辑 `sources.json` 的 `api_site`，按下面格式添加一项：

```json
"新源key": {
  "name": "源名称",
  "api": "https://example.com/api.php/provide/vod",
  "detail": "https://example.com"
}
```

| 字段 | 必填 | 说明 |
|------|------|------|
| `name` | 是 | 显示名称 |
| `api` | 是 | `provide/vod` 接口地址 |
| `detail` | 否 | 站点主页，用于报告中生成链接 |

添加后提交，GitHub Actions 会在下次定时运行时检测并更新健康版；也可先本地运行 `python check.py && python generate.py` 立即验证。

## 本地用法

```bash
# 检测（默认关键词）
python check.py

# 检测（指定关键词）
python check.py "斗罗大陆"

# 根据检测结果生成健康版订阅
python generate.py
```

执行顺序：先 `check.py` 生成报告，再 `generate.py` 生成健康版。

## 订阅使用

- 完整订阅（全部源）：直接使用 `sources.json`
- 健康订阅（只含检测通过的源）：使用 `dist/healthy.txt`（Base58）或 `dist/healthy.json`

```
https://raw.githubusercontent.com/<user>/<repo>/main/sources.json
https://raw.githubusercontent.com/<user>/<repo>/main/dist/healthy.txt
```

Base58 编码与 `bs58` 完全一致。

## 健康版说明

`healthy` 版本读取 `report.md` 中最近一次检测结果，只保留健康检测通过的源：

- 坏源自动从 `healthy.txt` 消失，恢复后下次检测通过会自动回来
- `sources.json` 始终保留全部源，不因检测失败被删除
- `report.md` 不存在时跳过健康版生成
- 新加入、尚未检测过的源不会进入健康版，直到下一次检测
- 默认只要健康检测通过即算通过；如需搜索也命中，把 `generate.py` 里 `REQUIRE_SEARCH_PASS` 改为 `True`

## 状态说明

| 状态 | 含义 |
|------|------|
| ✅ | 健康检测通过，搜索命中 |
| ⚠️ | 健康检测通过，但搜索无结果/不匹配 |
| ❌ | 健康检测失败 |
| 🚨 | 连续 3 天检测失败 |
| 🚫 | 已禁用，跳过检测 |
