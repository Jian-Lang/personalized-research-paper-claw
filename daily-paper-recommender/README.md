# dailypaper-skills

每日论文推荐子项目。它负责从本地会议接收列表 snapshot 里筛论文、生成推荐页，并把结果写进 Obsidian。

> 📺 [论文流水线效果演示（旧视频）](http://xhslink.com/o/1dhQCn40EWY) — 展示的是同一套工作流的早期版本

## 最新变更

- 会议推荐配置改为每个会议显式配置 `daily_take`，配比直接写在 `daily_papers.conferences` 里。
- 已纳入 ACL 2026；默认会议源为 ICML 2026、ICLR 2026、CVPR 2026、ACL 2026。
- 推荐配比直接由各会议项里的 `daily_take` 决定；要调整配比，只改对应会议的 `daily_take`。
- ACL 默认开启 `shuffle: true`，同步本地 JSONL snapshot 时会把 poster / finding 做稳定随机混排，避免先推荐完整主会再推荐 Findings。

## 🦴 这套东西会帮我做什么

- 每天抓一批新论文，做一轮初筛，生成推荐列表。
- 按 `daily_papers.conferences` 的会议配置和 `daily_take` 配比控制推荐来源。
- 用 title + abstract 的关键词偏好打分，并保留会议来源、列表顺序、paper/pdf 链接等元信息。
- 把推荐页写进 Obsidian，顺带维护目录页 / 导航页。
- 可选地为推荐论文生成详细笔记。

最终生成结果在 Obsidian 里大概会长这样：

```text
ObsidianVault/
├── DailyPapers/mocs/DailyPaperContent-YYYY-MM-DD.md
├── PaperNotes/.../*.md
└── PaperNotes/_concepts/.../*.md
```

可直接看模板：

- [Obsidian 模板](obsidian-templates/论文笔记模板.md)

## 🐕 怎么用

基本就 2 句：

```text
今日论文推荐
过去3天论文推荐
```

其他常见说法：

```text
过去一周论文推荐
跑一下论文抓取
跑一下论文点评
跑一下论文笔记
```

`今日论文推荐` 会跑完整流程。如果要读单篇论文、维护 personalized/domain 论文库，使用同级的 `../paper-note` 子项目。

```bash
./bin/daily-paper-recommend.sh
```

目录页一般会自动更新；如果你手动改过结构，或者怀疑没同步，再补一句：

```text
更新索引
```

## 🏡 安装

前置环境：

- Codex CLI
- [Obsidian](https://obsidian.md/)
- [Python 3.8+](https://www.python.org/)
- [`poppler-utils`](https://poppler.freedesktop.org/)（`apt install poppler-utils` / `brew install poppler`）
- [Zotero](https://www.zotero.org/)（可选）

建议给 Obsidian 库加上 git 版本管理。笔记多了以后有个版本历史会安心很多，也方便多设备同步。

如果你是在自己的本地机器上日常使用，通常直接用 `codex --full-auto` 会顺手很多；如果你明确已经在外部沙箱里，也可以用 `codex --dangerously-bypass-approvals-and-sandbox`，但风险更高，不建议在不熟悉的机器上直接这么跑。

在 `daily-paper-recommender` 目录运行：

```bash
mkdir -p ~/.codex/skills
cp -r ./skills/* ~/.codex/skills/

# 改成你自己的 Obsidian 库路径，要跟配置文件里的 paths.obsidian_vault 一致
VAULT=~/ObsidianVault
mkdir -p "$VAULT/DailyPapers" \
  "$VAULT/PaperNotes/_concepts/0-uncategorized" \
  "$VAULT/PaperNotes/_inbox"
```

## ⚙️ 配置

安装完之后需要改一下配置。配置文件是 `skills/_shared/user-config.local.json`，可以自己改，也可以直接让 Codex 按你的需求帮你改。

里面主要改这几项：

| 配置项 | 说明 |
| --- | --- |
| `paths.obsidian_vault` | 你的 Obsidian 库在哪 |
| `paths.zotero_db` | Zotero 数据库路径（不用 Zotero 可以不填） |
| `paths.zotero_storage` | Zotero 附件存储路径 |
| `daily_papers.conferences` | 每日推荐的会议、年份和单会议推荐数量列表，例如 `[{ "name": "ICML", "year": 2026, "daily_take": 5 }, { "name": "ICLR", "year": 2026, "daily_take": 5 }, { "name": "CVPR", "year": 2026, "daily_take": 5 }, { "name": "ACL", "year": 2026, "daily_take": 5, "shuffle": true }]`；数据源由代码内 registry 自动匹配 |
| `daily_papers.conferences[].daily_take` | 该会议每天最多推荐几篇论文；这是当前推荐的配比配置入口 |
| `daily_papers.conferences[].shuffle` | 是否在同步本地 JSONL snapshot 时做稳定随机混排；ACL 默认开启，用来混合 poster / finding |
| `daily_papers.daily_take` | 旧版全局 fallback；新配置建议不用它，优先写到每个会议项里 |
| `daily_papers.conference_preferences.keywords` | 你关心的关键词，只在论文 title + abstract 中匹配 |
| `daily_papers.conference_preferences.negative_keywords` | 排除关键词；title 或 abstract 命中一个就扣 100 分，通常不会进入推荐 |
| `daily_papers.conference_preferences.min_score` | 推荐阈值；title 命中一个关键词加 2 分，abstract 命中一个关键词加 1 分，默认 2 |

会议配比直接改这里：

```json
"conferences": [
  { "name": "ICML", "year": 2026, "daily_take": 5 },
  { "name": "ICLR", "year": 2026, "daily_take": 5 },
  { "name": "CVPR", "year": 2026, "daily_take": 5 },
  { "name": "ACL", "year": 2026, "daily_take": 5, "shuffle": true }
]
```

Zotero 配置主要用于后续详细笔记生成；只跑每日推荐时可以不填。

## 🦮 默认行为

默认 Obsidian 库管理不会自动commit、push：

- `auto_refresh_indexes = true`
- `git_commit = false`
- `git_push = false`

也就是默认会自动刷新目录页，但不会动你的 git。如果你的 Obsidian 库已经用 git 管理，希望跑完流程后自动提交，把 `git_commit` 打开就行。

## 🐾 大概怎么跑的

**每日推荐**现在走本地会议接收 JSONL snapshot，两步生成摘要式推荐：

1. **抓取**：Python 脚本读取 `conferences`，用代码内 registry 匹配 `data/paperlist` 下同步自 `ronpay/paperlist` 的 JSONL 文件。当前支持 ICML、ICLR、CVPR、ACL，默认都可配置到 2026。每个会议都有独立 cursor，会分别从各自本地 JSONL snapshot 顺序继续往下扫；如果会议项配置了 `shuffle: true`，`scripts/sync_paperlist.py` 会在同步 snapshot 时先做稳定随机混排。脚本读取 title、authors、abstract，并按 `conference_preferences` 计分。title 命中一个正向关键词加 2 分，abstract 命中一个正向关键词加 1 分；title 或 abstract 命中一个 negative keyword 扣 100 分。分数达到 `min_score` 才推荐。每个会议每天最多推荐该会议项里的 `daily_take` 篇、最多扫描 1000 篇；单日推荐总量由启用会议的 `daily_take` 加总决定。state 同时记录 title key，源顺序变化时不会重复推荐已经推过的论文。
2. **点评**：Codex 读候选列表，按 必读 / 值得看 / 可跳过 分流，基于摘要写推荐，保存到 Obsidian 的 `DailyPapers/` 目录，同时更新 `.history.json`。

刷新 accepted-paper snapshot 时运行：

```bash
python3 scripts/sync_paperlist.py
```

这个脚本只负责从 `ronpay/paperlist` 同步当前配置里的会议 JSONL；每日推荐本身不依赖网络。

默认不会为每日推荐生成细粒度论文笔记。需要给推荐论文补详细笔记时，再运行论文笔记步骤或使用 `../paper-note`。

**目录页**由 `generate-mocs` 维护：递归扫描论文笔记和概念库目录，自动生成带 wikilink 的索引页。

更多实现细节见 [ARCHITECTURE.md](ARCHITECTURE.md)。

## 🏠 仓库里有什么

平时真正常用的是每日推荐全流程；其他 skill 主要给调试、补笔记和目录维护用：

- `daily-papers`：每日推荐全流程
- `daily-papers-fetch`
- `daily-papers-review`
- `daily-papers-notes`
- `paper-reader`：给推荐论文补详细笔记
- `generate-mocs`：手动补刷目录页

## 🎾 进阶用法

如果你只想单独跑流水线某一步，也可以分别说：

```text
跑一下论文抓取
跑一下论文点评
跑一下论文笔记
```

如果你想做本地定时任务（比如每天早上 6 点自动运行），可以直接让 Codex 按你的系统环境帮你配置。

## 🐶 FAQ

**可以一步跑完整流程吗？**

可以。直接说 `今日论文推荐` 就行。内部拆成三步主要是为了避免单次上下文过长，同时方便单步调试和重跑。

**目录页会自动刷新吗？**

默认会。跑完整的每日推荐流程或论文笔记步骤时，结束后通常都会自动刷新一次。`更新索引` 更像是手动补刷入口。

**不用 Zotero 可以吗？**

可以。每日推荐不依赖 Zotero；Zotero 主要用于后续详细笔记和已有文献库检索。

**不用 Obsidian 可以吗？**

可以。输出本质上是 Markdown 文件，不强绑 Obsidian；只是如果你希望使用 `[[双向链接]]`、图谱和目录页索引，Obsidian 会更顺手。

**可以用来辅助论文写作吗？**

可以，比较适合用来整理 related work、维护笔记库和生成阅读提纲。AI 生成的内容建议自己核验后再使用。

**默认会动我的 git 仓库吗？**

不会。`commit / push` 默认关闭，只有你自己打开配置后才会执行。

## ⚠️ 免责声明

这是我个人研究工作流的开源整理。AI 生成的推荐、点评和笔记可能有事实错误或遗漏，所以更适合作为辅助工具，而不是直接替代你的研究判断。

另外，这套东西难免会有 bug，平台和环境适配问题也很正常；如果你遇到小问题，最省事的办法通常就是直接让 AI 帮你一起改。

## License

Apache-2.0. See `LICENSE`.
