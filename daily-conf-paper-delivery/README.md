# Daily Conf Paper Delivery

每日论文推荐子项目。它负责从本地会议接收列表里筛论文、生成推荐页，并把结果以 Markdown 写入全局笔记目录。

> 📺 [论文流水线效果演示（旧视频）](http://xhslink.com/o/1dhQCn40EWY) — 展示的是同一套工作流的早期版本

## 最新变更

- 会议推荐配置改为每个会议显式配置 `daily_take`，配比直接写在 `daily_papers.conferences` 里。
- 已纳入 ACL 2026；默认会议源为 ICML 2026、ICLR 2026、CVPR 2026、ACL 2026。
- 推荐配比直接由各会议项里的 `daily_take` 决定；要调整配比，只改对应会议的 `daily_take`。
- ACL 默认开启 `shuffle: true`，同步本地会议接收列表时会把 poster / finding 做稳定随机混排，避免先推荐完整主会再推荐 Findings。

## 🦴 这套东西会帮我做什么

- 每天抓一批新论文，做一轮初筛，生成推荐列表。
- 按 `daily_papers.conferences` 的会议配置和 `daily_take` 配比控制推荐来源。
- 用 title + abstract 的 topic / keyword 偏好打分，并保留命中原因、会议来源、列表顺序、paper/pdf 链接等元信息。
- 把推荐页写进 Obsidian，顺带维护目录页 / 导航页。
- 可选地为推荐论文生成详细笔记。

最终生成结果在 Obsidian 里大概会长这样：

```text
ResearchNotes/
└── DailyPapers/
    ├── mocs/DailyPaperContent-YYYY-MM-DD.md
    └── papers/.../*.md
```

可直接看模板：

- [Obsidian 模板](obsidian-templates/论文笔记模板.md)

## 🐕 怎么用

单次推荐直接说：

```text
今日论文推荐
过去3天论文推荐
过去一周论文推荐
```

定时推荐也直接说：

```text
每天早上 8 点推荐论文
把每日推荐改到 09:30
查看每日推荐定时状态
关闭每日论文推荐
```

`daily-papers` Skill 会在 macOS 上完成定时任务的安装、更新时间、状态检查或关闭，您不需要手动运行调度脚本。`今日论文推荐` 只跑一次，不会改变定时状态。

如果要读单篇论文、维护 personalized/domain 论文库，使用同级的 `../research-paper-noter` 子项目。

目录页一般会自动更新；如果您手动调整过结构，或者觉得内容没有同步，再补一句：

```text
更新索引
```

## 🏡 安装

前置环境：

- Codex CLI
- [Obsidian](https://obsidian.md/)（强烈推荐，但不是运行依赖）
- [Python 3.8+](https://www.python.org/)
- [`poppler-utils`](https://poppler.freedesktop.org/)（`apt install poppler-utils` / `brew install poppler`）
- [Zotero](https://www.zotero.org/)（可选）

建议给 Obsidian 库加上 git 版本管理。笔记多了以后有个版本历史会安心很多，也方便多设备同步。

如果您是在自己的本地机器上日常使用，通常直接用 `codex --full-auto` 会顺手很多；如果您明确已经在外部沙箱里，也可以用 `codex --dangerously-bypass-approvals-and-sandbox`，但风险更高，不建议在不熟悉的机器上直接这么跑。

从仓库根目录运行。推荐使用符号链接，让 Skill 始终读取当前 checkout 中的配置、脚本和会议数据，并让自然语言定时管理准确定位调度工具：

```bash
SKILLS_DIR="${CODEX_HOME:-$HOME/.codex}/skills"
mkdir -p "$SKILLS_DIR"

ln -s "$PWD/daily-conf-paper-delivery/skills/_shared" "$SKILLS_DIR/_shared"
ln -s "$PWD/daily-conf-paper-delivery/skills/daily-papers" "$SKILLS_DIR/daily-papers"
ln -s "$PWD/daily-conf-paper-delivery/skills/daily-papers-fetch" "$SKILLS_DIR/daily-papers-fetch"
ln -s "$PWD/daily-conf-paper-delivery/skills/daily-papers-review" "$SKILLS_DIR/daily-papers-review"
ln -s "$PWD/daily-conf-paper-delivery/skills/daily-papers-notes" "$SKILLS_DIR/daily-papers-notes"
ln -s "$PWD/daily-conf-paper-delivery/skills/paper-reader" "$SKILLS_DIR/paper-reader"
ln -s "$PWD/daily-conf-paper-delivery/skills/generate-mocs" "$SKILLS_DIR/generate-mocs"

# 全局 Markdown 根目录只在仓库根配置一次
cp config/user-config.example.json config/user-config.local.json

# Daily 子项目只保存会议和兴趣偏好
cp daily-conf-paper-delivery/skills/_shared/user-config.example.json \
  daily-conf-paper-delivery/skills/_shared/user-config.local.json
```

编辑根级 `config/user-config.local.json` 中的 `paths.markdown_root`。第一次运行会自动创建 `DailyPapers/mocs` 和 `DailyPapers/papers`，不需要手动 `mkdir`。

## ⚙️ 配置

全局 Markdown 根目录位于仓库根级 `config/user-config.local.json`。本目录下的 `skills/_shared/user-config.local.json` 只保存 Daily 专属配置，您可以自行修改，也可以直接告诉 Codex 您想如何调整。

首次配置可以从 `skills/_shared/user-config.example.json` 复制；运行时只读取 `user-config.local.json`。

里面主要改这几项：

| 配置项 | 说明 |
| --- | --- |
| `daily_papers.conferences` | 每日推荐的会议、年份和单会议推荐数量列表，例如 `[{ "name": "ICML", "year": 2026, "daily_take": 5 }, { "name": "ICLR", "year": 2026, "daily_take": 5 }, { "name": "CVPR", "year": 2026, "daily_take": 5 }, { "name": "ACL", "year": 2026, "daily_take": 5, "shuffle": true }]`；本地文件按 `<CONF>/<conf>_<year>.jsonl` 自动匹配 |
| `daily_papers.conferences[].daily_take` | 该会议每天最多推荐几篇论文；这是当前推荐的配比配置入口 |
| `daily_papers.conferences[].shuffle` | 是否在同步本地会议接收列表时做稳定随机混排；ACL 默认开启，用来混合 poster / finding |
| `daily_papers.daily_take` | 旧版全局 fallback；新配置建议不用它，优先写到每个会议项里 |
| `daily_papers.scan_limit` | 每个会议从当前 cursor 向后最多扫描多少篇，默认 1000；达到上限时，即使未选满 `daily_take` 也会停止 |
| `daily_papers.topics` | 研究方向，同时作为点评页分类；title 或 abstract 完整命中一个 topic 加 1 分 |
| `daily_papers.keywords` | 具体方法名和同义表达；title 完整命中加 3 分，否则 abstract 完整命中加 1 分 |
| `daily_papers.exclude_keywords` | 排除词；title 或 abstract 完整命中一个就计 -100 分 |
| `daily_papers.min_score` | 推荐阈值，默认 2；topic 单独命中不足以入选 |
| `automation.auto_refresh_indexes` | 本次流程结束后是否刷新目录页；不会自动发起推荐 |
| `automation.git_commit` | 是否在流程完成后自动 commit；默认关闭 |
| `automation.git_push` | 是否在自动 commit 后继续 push；默认关闭 |
| `automation.daily_run_time` | macOS 每日自动运行时间，24 小时制 `HH:MM`；默认 `08:00` |

会议配比直接改这里：

```json
"conferences": [
  { "name": "ICML", "year": 2026, "daily_take": 5 },
  { "name": "ICLR", "year": 2026, "daily_take": 5 },
  { "name": "CVPR", "year": 2026, "daily_take": 5 },
  { "name": "ACL", "year": 2026, "daily_take": 5, "shuffle": true }
]
```

Zotero 配置主要用于后续详细笔记生成；只跑每日推荐时不需要配置。

## 🦮 默认行为

默认 Obsidian 库管理不会自动commit、push：

- `auto_refresh_indexes = true`
- `git_commit = false`
- `git_push = false`
- `daily_run_time = "08:00"`

这些都是 Daily 自己的运行后行为：默认会刷新目录页，但不会改动您的 git，也不会因为配置存在就自动开始推荐。`daily_run_time` 只有在安装调度任务后才会生效；手动触发会立即运行。如果您的 Obsidian 库已经用 git 管理，希望跑完流程后自动提交，把 `git_commit` 打开就行。

## 🐾 大概怎么跑的

**每日推荐**现在读取本地会议接收 JSONL 列表，两步生成一页式每日论文推荐：

1. **抓取**：Python 脚本读取 `conferences`，按 `data/paperlist/<CONF>/<conf>_<year>.jsonl` 的约定匹配仓库内会议接收列表。当前仓库提供 ICML、ICLR、CVPR、ACL。每个会议都有独立 cursor（上次扫描到列表第几篇的进度记录）；`shuffle: true` 只在导入列表时做稳定随机混排。topic 在 title 或 abstract 中完整命中加 1 分；keyword 在 title 中完整命中加 3 分，否则在 abstract 中完整命中加 1 分；exclude keyword 命中计 -100 分。大小写和标点会规范化，匹配按完整词/短语边界执行，重复项只计一次。分数达到 `min_score` 才推荐。每个会议每天最多推荐自己的 `daily_take` 篇，并从当前 cursor 向后最多扫描 `scan_limit` 篇（默认 1000）；达到任一上限或走到列表末尾即停止。
2. **汇总与点评**：Codex 读候选列表及 `score_breakdown`，以同一份 `topics` 做阅读分流和主题分类，为每篇生成包含元信息、双语摘要、背景、动机、方法、评估、借鉴意义与锐评的摘要式笔记，再把当天的全部推荐集中写入同一张页面，保存到 Obsidian 的 `DailyPapers/` 目录，同时更新 `.history.json`。推荐页 frontmatter 的 topics / keywords 也直接来自这两项配置。

本项目会为每一个新的重要会议提供接收论文列表更新；更新仓库后即可使用新增数据。

如果要自行维护其他会议，可以直接按 `data/paperlist/<CONF>/<conf>_<year>.jsonl` 的路径放入兼容 JSONL；每行至少包含 `title` 和 `abstract`，再把会议加入 `daily_papers.conferences`。已有相同目录结构的本地数据时，也可以运行：

```bash
python3 scripts/sync_paperlist.py --source-dir /path/to/local/paperlist
```

这个脚本只从您指定的本地目录复制当前配置里的会议 JSONL；每日推荐本身不依赖外部论文列表仓库。

默认不会为每日推荐生成细粒度论文笔记。需要给推荐论文补详细笔记时，再运行论文笔记步骤或使用 `../research-paper-noter`。

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

如果您只想单独运行流水线的某一步，也可以分别说：

```text
跑一下论文抓取
跑一下论文点评
跑一下论文笔记
```

如果您需要排障或不经过 Codex，可以直接管理底层调度：

```bash
./bin/configure-schedule.sh --time 08:00
./bin/configure-schedule.sh --status
./bin/configure-schedule.sh --remove
```

当前自动调度支持 macOS launchd，并使用系统本地时间。底层脚本不是日常使用的必要入口。

## 🐶 FAQ

**可以一步跑完整流程吗？**

可以。直接说 `今日论文推荐` 就行。默认内部串联抓取与摘要式点评；详细论文笔记是可选的第三步，不会自动执行。

**目录页会自动刷新吗？**

默认会。跑完整的每日推荐流程或论文笔记步骤时，结束后通常都会自动刷新一次。`更新索引` 更像是手动补刷入口。

**不用 Zotero 可以吗？**

可以。每日推荐不依赖 Zotero；Zotero 主要用于后续详细笔记和已有文献库检索。

**不用 Obsidian 可以吗？**

可以。输出本质上是 Markdown 文件，不强绑 Obsidian。不过强烈推荐安装 Obsidian，然后选择“Open folder as vault / 打开文件夹作为仓库”，打开根配置中的 `markdown_root`。无需提前创建笔记，也无需开启 Obsidian Sync。

**可以用来辅助论文写作吗？**

可以，比较适合用来整理 related work、维护笔记库和生成阅读提纲。AI 生成的内容建议自己核验后再使用。

**默认会动我的 git 仓库吗？**

不会。`commit / push` 默认关闭，只有您主动打开配置后才会执行。

## ⚠️ 免责声明

这套工具来自真实的研究工作流。AI 生成的推荐、点评和笔记可能有事实错误或遗漏，因此更适合作为您的研究助手，而不应替代您的研究判断。

另外，这套工具难免会有 bug，平台和环境适配问题也很正常；如果您遇到小问题，最省事的办法通常是直接请 AI 和您一起排查、一起改。

## License

Apache-2.0. See `LICENSE`.
