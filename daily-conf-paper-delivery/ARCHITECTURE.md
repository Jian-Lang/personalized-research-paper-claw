# Daily Conf Paper Delivery Architecture

这份文档记录各模块的实现逻辑，方便想改代码或理解内部机制的人参考。

## 整体架构

```
用户说一句话
    │
    ├─ "今日论文推荐" ──→ daily-papers（编排器）
    │                        ├─ Step 1: daily-papers-fetch（Python，零 token）
    │                        ├─ Step 2: daily-papers-review（Codex 点评）
    │                        └─ Step 3: daily-papers-notes（Codex + paper-reader）
    │
    ├─ "读一下这篇论文" ──→ paper-reader（独立 skill）
    │
    └─ "更新索引" ──→ generate-mocs（Python 脚本）
```

三步流水线的设计主要是为了控制单次上下文长度。每步之间通过 `/tmp` 下的 JSON 文件传数据。

---

## Step 1: daily-papers-fetch

**纯 Python，不消耗 Codex token。**

### 1.1 抓取 + 打分（fetch_and_score.py）

数据源：
- 仓库内 `data/paperlist/<CONF>/<conf>_<year>.jsonl` 会议接收列表 snapshot
- snapshot 随仓库更新，也可按相同目录结构手动添加
- 当前仓库提供 ICML、ICLR、CVPR、ACL；兼容 JSONL 可按目录约定加入其他会议
- 每个会议由独立 cursor 控制扫描进度

打分规则：
- `topics`：title 或 abstract 完整命中一个 topic 加 1 分
- `keywords`：title 完整命中加 3 分，否则 abstract 完整命中加 1 分
- `exclude_keywords`：title 或 abstract 完整命中任一项时计 -100 分
- 大小写和标点统一规范化，按完整词/短语边界匹配；等价重复项只计算一次
- 分数达到 `min_score` 才进入候选，默认阈值为 2

去重与进度：
- 每个会议维护独立 cursor、已推荐 source id 和规范化标题 key
- 同一天重复运行默认复用当天缓存，`--force` 才继续推进
- `days > 1` 时，目标数量和最大扫描窗口同步乘以天数
- 每篇候选输出 `score_breakdown`，供点评阶段解释命中原因和优先分类

输出：`/tmp/daily_papers_top30.json`

### 1.2 元数据富化（enrich_papers.py）

会议 JSONL 已提供 title、authors、abstract、会议页和 PDF。富化脚本规范化字段；能定位 arXiv 时再补充首图和可读链接。

保留内容：
- title、authors、abstract、conference、venue、source rank
- paper URL、PDF、首图 URL
- score 与 `score_breakdown`

输出：`/tmp/daily_papers_enriched.json`

---

## Step 2: daily-papers-review

**Codex 主导，读候选列表写点评。**

### 2.1 扫描已有笔记

Glob 扫描 Obsidian 的论文笔记和概念库目录，把候选论文跟已有笔记做匹配（方法名 / 标题模糊匹配），标记 `has_existing_note`。

### 2.2 写锐评

Codex 以配置中的 `topics` 作为研究方向和输出分类，点评每篇论文：
- 分流表：🔥 必读 / 👀 值得看 / 💤 可跳过
- 每篇包含：作者、机构、链接、来源、核心方法（带 `[[概念]]` 链接）、对比方法、借鉴意义、锐评
- 已有笔记的论文走简化格式
- 跟用户方向完全无关的论文可以跳过，列出跳过原因

硬性约束：
- 不能凭空说"只有仿真"——必须检查 `has_real_world` 字段
- 不能说某篇是"山寨"——除非有具体方法论证据
- 不确定的信息必须注明"摘要未提及"

### 2.3 保存

- 写入 `{DAILY_MOCS_PATH}/DailyPaperContent-YYYY-MM-DD.md`
- 更新 `.history.json`：追加今日推荐的 arXiv ID + 标题，只保留最近 30 天
- 可选：git commit

---

## Step 3: daily-papers-notes

**Codex 编排 + 多次调用 paper-reader。**

### 3.1 概念库补充

1. 扫描推荐文件里所有 `[[概念]]` 链接 + enriched JSON 的 `method_names`
2. 过滤：只保留方法 / 模型 / 数据集 / 仿真器 / 技术概念名，排除通用词、论文标题、人名
3. 自动分类到 16 个概念子目录（生成模型 / 强化学习 / 机器人策略 / 3D 视觉 / 仿真器 / 数据集等）
4. 创建概念笔记：定义 + 数学形式 + 核心要点 + 代表工作 + 相关概念

### 3.2 论文笔记生成

- 只为"🔥 必读"论文生成完整笔记
- 已有笔记如果 < 100 行或缺少关键 section → 删除重新生成
- 逐篇调用 paper-reader skill

质量校验（每篇）：
- 文件 ≥ 120 行
- 包含 LaTeX 公式（≥ 2 处）
- 包含图片引用（≥ 1 处）
- 包含 `## 关键公式` 和 `## 实验结果` section
- 不达标 → 删了重来

### 3.3 链接回填

在推荐文件中，给已有笔记的论文插入 `📒 **笔记**: [[NoteName]]` 链接。

### 3.4 刷新目录页 + git

- 调用 `generate_concept_mocs.py` 和 `generate_paper_mocs.py`
- 可选：git commit & push

---

## paper-reader

**作为独立 skill 运行，完整工具链（Bash / Read / Write / Edit / WebFetch / WebSearch）。**

### 输入源

| 来源 | 处理方式 |
|------|----------|
| arXiv 链接 | WebFetch 抓取 |
| 本地 PDF | 直接读取 |
| Zotero 搜索 | 查 DB → 定位 PDF / 在线源 |
| Zotero 分类批量 | 递归子分类 → 去重 → 逐篇处理 |

找不到 PDF 时的 fallback 顺序：
1. `zotero_helper.py info` 拿元数据
2. 提取 arXiv ID → WebFetch HTML 版本（优先，能拿图）
3. Fallback：PDF 版本 / DOI 页面
4. 最后：WebSearch 论文标题
5. 都不行 → 跳过

### 阅读模式

| 模式 | 触发词 | 输出 |
|------|--------|------|
| 快速摘要 | "快速看一下" | 3-5 句核心贡献 |
| 完整解析 | 默认 | 结构化笔记（模板） |
| 批判性分析 | "批判性分析" | 优缺点评估 |
| 知识提取 | "提取公式" | 公式 + 算法伪代码 |

### 图片获取（多路 fallback）

1. arXiv HTML：提取 `<figure>` 标签的图片 URL（优先）
2. 项目主页：从摘要 / HTML 找项目链接，抓 teaser 图
3. PDF 提取：`pdfimages -png`，过滤 > 10KB 的
4. 写完后跑 `download_note_images.py` 做可达性检查，不可达的自动下载到本地

### 笔记生成

严格按 `paper-note-template.md` 模板：
- 所有 Figure、所有公式、所有 Table 都必须出现
- 技术术语首次出现必须用 `[[概念]]` 链接
- 每个公式需要：名称、LaTeX、含义、符号说明
- 文件名只用方法 / 模型名（如 `Pi05.md`），不加年份前缀

### 存储

- 路径：`{NOTES_PATH}/{zotero_collection_path}/{MethodName}.md`
- 不确定分类 → `_inbox/`
- YAML frontmatter：title / method_name / authors / year / venue / tags / zotero_collection / image_source / created

### 概念库维护

每篇论文读完后：
1. 扫描笔记中所有 `[[概念]]` 链接
2. 检查概念笔记是否存在
3. 不存在的按 16 类自动分类并创建

### 批量处理（paper_daemon.py）

```bash
python3 paper_daemon.py -c "VLA"     # 处理 VLA 分类
python3 paper_daemon.py --status     # 查看进度
python3 paper_daemon.py --list       # 列出所有分类
```

- API 限流：指数退避（60s → 最大 12h）
- 配额监控：每 3 篇检查一次，> 85% 自动等待
- 断点续跑：checkpoint 持久化
- 进程锁：防止并发
- 自动跳过已有笔记（> 100 行）

---

## generate-mocs

**纯 Python，递归扫目录生成索引页。**

核心函数 `build_tree_mocs()`：
- 递归遍历目录
- 每个目录生成一个 `目录名.md` 索引文件
- 包含：子目录链接（带笔记数统计）+ 当前目录笔记列表
- 幂等：内容没变的文件不重写
- 用 wikilink 格式

分两个入口：
- `generate_concept_mocs.py`：扫描概念库（`_概念/`）
- `generate_paper_mocs.py`：扫描论文笔记（排除概念目录）

---

## _shared 公共模块

### 根级全局配置

所有工作流共用仓库根目录的 `config/user-config.local.json`。它只负责全局 Markdown 根目录：

```json
{
  "paths": {
    "markdown_root": "~/ResearchNotes"
  }
}
```

### Daily 专属配置

`skills/_shared/user-config.local.json` 保存会议、topics、关键词、打分阈值，以及 Daily 自己的运行后行为和定时时间：

```json
{
  "daily_papers": {
    "conferences": [
      {"name": "ICML", "year": 2026, "daily_take": 5},
      {"name": "ICLR", "year": 2026, "daily_take": 5}
    ],
    "topics": ["MLLM Personalization", "LLM Abstention"],
    "keywords": ["personalized mllm", "llm abstention"],
    "exclude_keywords": ["medical", "robotic"],
    "min_score": 2
  },
  "automation": {
    "auto_refresh_indexes": true,
    "git_commit": false,
    "git_push": false,
    "daily_run_time": "08:00"
  }
}
```

### user_config.py

子项目的 `user_config.py` 是根级 `config/project_config.py` 的薄入口。它从根级配置读取 Markdown 位置，从当前子项目配置读取自动化行为，并提供按需创建 Daily、Personalized、Domain 目录的函数。

`daily-papers` Skill 同时路由单次推荐与自然语言定时管理。定时分支调用 `bin/configure-schedule.sh` 的 `--time`、`--status` 或 `--remove` 接口；脚本以结构化方式更新 `automation.daily_run_time`，生成并加载 macOS launchd plist。时间使用系统本地时区；手动触发推荐不经过调度器，也不改变调度状态。

### moc_builder.py

MOC 生成引擎，被 `generate_concept_mocs.py` 和 `generate_paper_mocs.py` 调用。

---

## Markdown 目录结构

```
~/ResearchNotes/
├── DailyPapers/
│   ├── mocs/DailyPaperContent-YYYY-MM-DD.md
│   ├── papers/
│   └── .history.json                # 跨天去重索引
├── PersonalizedPaper/
└── DomainPapers/
```
