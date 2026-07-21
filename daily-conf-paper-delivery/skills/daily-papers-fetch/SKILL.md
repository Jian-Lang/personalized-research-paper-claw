---
name: daily-papers-fetch
description: |
  论文抓取（会议推荐流水线的第 1 步）。从仓库内的会议接收 JSONL snapshot 获取论文，按 title + abstract
  的 topic / keyword 偏好打分筛选，富化信息，
  输出到 /tmp/daily_papers_enriched.json 供后续 skill 使用。

  触发词："论文抓取"、"跑一下论文抓取"
  支持多天模式："过去3天论文推荐"、"过去一周论文推荐"、"过去一周的论文"、"抓 3 天的论文"、"最近5天"
---

> **开始前**: 先说一声 "开始抓取论文 🐕" 并告知今天日期。如果是多天模式，告知抓取范围。

# 会议论文抓取 (Fetch + Score + Enrich)

你是 用户的论文抓取系统（3 步流水线的第 1 步）。抓取最新论文 → 打分筛选 → 富化信息 → 保存到临时文件。

## Step 0: 读取共享配置

先通过 `../_shared/user_config.py` 读取配置。全局 Markdown 根目录来自仓库根目录的 `config/user-config.local.json`，Daily 专属筛选配置来自 `../_shared/user-config.local.json`；未配置字段回退到代码默认值。

显式生成并在后续统一使用这些变量：

- `VAULT_PATH`
- `DAILY_PROJECT_PATH`
- `DAILY_MOCS_PATH`
- `TOPICS`
- `KEYWORDS`
- `EXCLUDE_KEYWORDS`
- `CONFERENCE_SOURCES`
- `MIN_SCORE`

其中：

- `DAILY_PROJECT_PATH = {VAULT_PATH}/{daily_papers_folder}`
- `DAILY_MOCS_PATH = {DAILY_PROJECT_PATH}/{project_mocs_folder}`
- 所有关键词、阈值都以共享配置为准。
- 当前项目只读取本仓库 `data/paperlist/<CONF>/<conf>_<year>.jsonl` 的会议接收 JSONL，由 `daily_papers.conferences` 控制，并按会议名和年份匹配本地文件。
- topic 写在 `daily_papers.topics`，同时作为研究方向和点评页分类；任一 topic 在 title 或 abstract 中完整命中加 1 分。
- 关键词写在 `daily_papers.keywords`，只匹配论文 `title + abstract`；关键词在 title 中完整命中加 3 分，否则在 abstract 中完整命中加 1 分。
- 排除词写在 `daily_papers.exclude_keywords`，只要 title 或 abstract 完整命中一个就记为排除并计 -100 分。
- 推荐阈值写在 `daily_papers.min_score`。默认是 2，表示 topic 单独命中不足以入选，必须再有关键词或其他 topic 支撑。
- 匹配会统一大小写和标点，并按完整词/短语边界判断；配置中的大小写或连字符等价重复项只计算一次。
- 会议、年份和每个会议每天最多推荐数量写在 `daily_papers.conferences`，例如 `[{ "name": "ICML", "year": 2026, "daily_take": 5 }, { "name": "ICLR", "year": 2026, "daily_take": 5 }, { "name": "CVPR", "year": 2026, "daily_take": 5 }, { "name": "ACL", "year": 2026, "daily_take": 5, "shuffle": true }]`。用户不需要配置 adapter 类型或 URL。
- `daily_take` 优先写在每个会议项里；旧版全局 `daily_papers.daily_take` 只作为兼容 fallback。
- `shuffle: true` 表示同步本地 JSONL snapshot 时做稳定随机混排；ACL 默认开启，用来混合 poster / finding，避免主会先跑完再跑 Findings。

后续统一以共享配置和上面的变量为准。

## 解析天数

从用户输入中解析 `--days N` 参数。匹配规则：
- "过去一周"、"最近7天"、"一周的论文" → `--days 7`
- "过去3天"、"最近三天"、"抓3天" → `--days 3`
- "过去两周" → `--days 14`
- 无特殊指定 / "跑一下论文抓取" → 不加 `--days`（默认当天）

将解析出的天数存为变量 `DAYS_ARG`，在后续脚本调用中使用。

## 配置来源

- 用户配置文件在 `../_shared/user-config.local.json`
- 未配置的字段回退到代码内置默认值

## 工作流程

### Phase 1+2: 抓取 + 打分 + cursor 去重（纯 Python 脚本）

用 `fetch_and_score.py` 一步完成会议 JSONL 获取、关键词打分、cursor + 标题去重、选取每日候选。**零 token 消耗。**

```bash
# 默认：当天
python3 ../daily-papers/fetch_and_score.py > /tmp/daily_papers_top30.json

# 多天模式（将 N 替换为解析出的天数）
python3 ../daily-papers/fetch_and_score.py --days N > /tmp/daily_papers_top30.json
```

根据前面解析的 `DAYS_ARG`，如果用户指定了天数就加 `--days N`，否则不加。

脚本自动完成：
- 读取 `daily_papers.conferences`，按会议名和年份解析本地 JSONL 路径
- 当前仓库提供 ICML、ICLR、CVPR、ACL；其他会议也可按相同目录和 JSONL 格式加入
- 每个会议按各自 source cursor 扫描本地 JSONL snapshot，默认每个会议每天最多扫描 1000 篇；`shuffle: true` 的会议在同步 snapshot 时已经完成稳定随机混排
- 只基于 JSONL 中的 title + abstract 做 topic / keyword 打分
- topic 命中加 1 分；关键词命中 title 加 3 分，否则命中 abstract 加 1 分
- 命中 `daily_papers.exclude_keywords` 中任一排除词时计 -100 分
- 分数达到 `daily_papers.min_score` 才推荐；每个会议每天最多推荐该会议配置的 `daily_take` 篇
- 每篇输出 `score_breakdown`，记录命中的 topics、title keywords、abstract keywords 和 exclude keywords
- 每个会议凑满自己的 `daily_take` 就立刻停止；单日推荐总量由启用会议的 `daily_take` 加总决定
- 用仓库内 `state/conference-state.json` 记录每个会议源的 cursor、已推荐 paper id 和标题 key，避免 JSONL 顺序变化或源切换后重复推荐；旧版 `{DAILY_PROJECT_PATH}/.conference-state.json` 只作为兼容读取路径
- 同一天重复运行默认复用当天缓存，不会继续推进 cursor；需要强制推进时手动加 `--force`

进度日志输出到 stderr，JSON 结果输出到 stdout。

**检查输出**：确认 `/tmp/daily_papers_top30.json` 存在且包含有效 JSON 数组。如果为空数组或文件不存在，检查 stderr 诊断问题。

### Phase 3: 批量富化（enrich_papers.py 脚本）

用 `enrich_papers.py` 脚本一次性整理所有论文字段。JSONL 已经提供 title / authors / abstract / url / pdf；如果没有 arXiv id，富化脚本不会再去抓 arXiv，只补齐空的结构化字段。

**先把 Phase 2 的 Top 30 结果保存到临时文件**，然后运行：

```bash
cat /tmp/daily_papers_top30.json | python3 ../daily-papers/enrich_papers.py /tmp/daily_papers_enriched.json
```

注意：使用**文件路径参数**（而非 stdout 重定向），避免 sandbox 环境下 stdout/stderr 混淆。

脚本自动完成以下工作：
- 对会议论文：保留 JSONL 提供的 title、authors、abstract、conference、venue、source_rank、has_paper、paper_url、pdf
- 对带 arXiv id 的论文：继续按旧逻辑补充 arXiv HTML / PDF 信息

**输出格式**：与输入相同的 JSON 数组，每篇论文增加以下字段：
- `figure_url` (string): 首图 URL
- `affiliations` (string): 机构列表，逗号分隔
- `authors` (string): 作者列表（可能被更完整的来源覆盖）
- `section_headers` (array): 章节标题
- `captions` (array): 图表标题
- `has_real_world` (bool): 是否包含真实实验
- `method_names` (array): 方法名列表
- `method_summary` (string): 方法描述（300-500 字）
- `conference` (string): 会议名，例如 ICML
- `venue` (string): 会议年份，例如 ICML 2026
- `source_rank` (int): 论文在会议列表中的 0-based 顺序
- `source_rank_display` (int): 论文在会议列表中的 1-based 顺序
- `has_paper` (bool): 是否抓到 PDF / OpenReview / arXiv 等 paper 链接
- `paper_url` (string): 非 PDF paper 链接（如果有）

## 输出

完成后检查 `/tmp/daily_papers_enriched.json` 存在且包含有效 JSON 数组。告知用户：
- 抓取了多少篇论文
- 富化成功多少篇
- 提示运行下一步：`跑一下论文点评`

## 注意事项

- Phase 1+2 使用 `fetch_and_score.py` 脚本，由当前 Codex 会话直接执行，零 token 消耗
- Phase 3 使用 `enrich_papers.py` 脚本，同样由当前 Codex 会话直接执行
- 如果脚本执行失败，检查 stderr 输出诊断问题
- 如果总论文数不足配置目标，有多少处理多少
- **不做 git 操作**，不生成推荐文件，只输出临时 JSON
