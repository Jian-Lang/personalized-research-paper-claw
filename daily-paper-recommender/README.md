# dailypaper-skills

我平时读论文用的一套 Codex skills。直接跟 Codex 说一句话，就能筛论文、读论文、写笔记，最后自动存进 Obsidian。

> 📺 [论文流水线效果演示（旧视频）](http://xhslink.com/o/1dhQCn40EWY) — 展示的是同一套工作流的早期版本

## 🦴 这套东西会帮我做什么

- 每天抓一批新论文，做一轮初筛，生成推荐列表。
- 对单篇论文做完整解析、快速摘要或批判性分析。
- 把论文里的术语顺手沉成概念笔记，方便后面继续连。
- 把内容写进 Obsidian，顺带维护目录页 / 导航页。
- 能接 Zotero，所以不用一篇篇复制链接。

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
读一下这篇论文 https://arxiv.org/abs/2509.24527
```

其他常见说法：

```text
过去3天论文推荐
过去一周论文推荐

读一下这篇论文 ~/Downloads/paper.pdf
快速看一下这篇论文 https://arxiv.org/abs/2509.24527
批判性分析这篇论文 ~/Downloads/paper.pdf

读一下 Zotero 里的 Diffusion Policy
批量读一下 Zotero 里 VLA 分类下的论文
```

`今日论文推荐` 会跑完整流程，`读一下这篇论文 ...` 用来读单篇。

如果是你主动收集的一批论文，可以用手动阅读入口。它会复用同一套详细笔记模板，并把论文追加到 `PersonalizedPaper/mocs/PersonalizedPaperContent.md`；这个汇总只按主题累计论文，不包含每日推荐里的「今日锐评」和「分流表」。

```bash
./bin/paper-read.sh "Paper title or arXiv URL"
./bin/paper-read.sh "Title 1" "Title 2"
./bin/paper-read.sh /path/to/titles.txt
```

如果是按某个 domain 长期整理 related work，用 domain 入口。它会写入配置里的独立 domain vault；结构是 `{domain}/paper` 和 `{domain}/content`。`paper` 是完整详细笔记，`content` 复用 manual 的汇总条目结构，按你给的子类别维护，并按论文年份排序。

```bash
./bin/domain-paper-add.sh "TTA" "multimodal TTA" "Paper title or arXiv URL"
./bin/domain-paper-add.sh "TTA" "VLM TTA" "Title 1" "Title 2"
./bin/domain-paper-add.sh "TTA" "multimodal TTA" /path/to/titles.txt
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

在仓库根目录运行：

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

安装完之后建议创建本地配置。没有本地配置时会使用代码内置默认值，但正式使用时应该从示例复制一份再改：

```bash
cp skills/_shared/user-config.example.json skills/_shared/user-config.local.json
```

配置文件是 `skills/_shared/user-config.local.json`，可以自己改，也可以直接让 Codex 按你的需求帮你改。

里面主要改这几项：

| 配置项 | 说明 |
| --- | --- |
| `paths.obsidian_vault` | 你的 Obsidian 库在哪 |
| `paths.manual_papers_folder` | 手动阅读累计汇总目录，默认 `PersonalizedPaper` |
| `paths.domain_papers_vault` | domain 论文独立 Obsidian 库路径 |
| `paths.domain_paper_folder` | domain 内详细笔记目录，默认 `paper` |
| `paths.domain_content_folder` | domain 内分类汇总目录，默认 `content` |
| `paths.zotero_db` | Zotero 数据库路径（不用 Zotero 可以不填） |
| `paths.zotero_storage` | Zotero 附件存储路径 |
| `daily_papers.conferences` | 每日推荐的会议和年份列表，例如 `[{ "name": "ICML", "year": 2026 }, { "name": "ICLR", "year": 2026 }]`；抓取源由代码内 registry 自动匹配 |
| `daily_papers.daily_take` | 每个会议每天最多推荐几篇论文，默认 5 |
| `daily_papers.conference_preferences.keywords` | 你关心的关键词，只在论文 title + abstract 中匹配 |
| `daily_papers.conference_preferences.negative_keywords` | 排除关键词；title 或 abstract 命中一个就扣 100 分，通常不会进入推荐 |
| `daily_papers.conference_preferences.min_score` | 推荐阈值；title 命中一个关键词加 2 分，abstract 命中一个关键词加 1 分，默认 2 |

`批量读一下 Zotero 里 XXX 分类下的论文` 不需要额外的映射文件；只要 `paths.zotero_db` 和 `paths.zotero_storage` 配对，脚本会直接从你的 Zotero 分类树里查。

## 🦮 默认行为

默认 Obsidian 库管理不会自动commit、push：

- `auto_refresh_indexes = true`
- `git_commit = false`
- `git_push = false`

也就是默认会自动刷新目录页，但不会动你的 git。如果你的 Obsidian 库已经用 git 管理，希望跑完流程后自动提交，把 `git_commit` 打开就行。

## 🐾 大概怎么跑的

**每日推荐**现在走会议接收列表，两步生成摘要式推荐：

1. **抓取**：Python 脚本读取 `conferences`，用代码内 registry 匹配会议源。当前支持 ICML 和 ICLR：ICML 解析 `https://icml.cc/Downloads/{year}`，ICLR 解析 `https://papers.cool/venue/ICLR.{year}`。每个会议都有独立 cursor，会分别从各自会议列表 cursor 位置继续往下扫，读取 title、authors、abstract，并按 `conference_preferences` 计分。title 命中一个正向关键词加 2 分，abstract 命中一个正向关键词加 1 分；title 或 abstract 命中一个 negative keyword 扣 100 分。分数达到 `min_score` 才推荐。默认每个会议每天最多推荐 `daily_take` 篇、最多扫描 120 篇；凑满就立刻停止，cursor 推进到实际停止位置；如果扫描 120 篇后仍不足，就按实际数量输出，并把 cursor 推进到当天扫描边界。
2. **点评**：Codex 读候选列表，按 必读 / 值得看 / 可跳过 分流，基于摘要写推荐，保存到 Obsidian 的 `DailyPapers/` 目录，同时更新 `.history.json`。

默认不会为每日推荐生成细粒度论文笔记。只有候选里抓到了 PDF / OpenReview / arXiv 等 paper 链接，并且你明确说“读一下这篇”，才走 paper-reader。

**读单篇**走 paper-reader：支持 arXiv 链接、本地 PDF、Zotero 搜索。会从 arXiv HTML / 项目主页 / PDF 多路取图，按模板生成结构化笔记，自动归类到 Obsidian 对应目录。

**目录页**由 `generate-mocs` 维护：递归扫描论文笔记和概念库目录，自动生成带 wikilink 的索引页。

更多实现细节见 [ARCHITECTURE.md](ARCHITECTURE.md)。

## 🏠 仓库里有什么

平时真正常用的是前 2 个，后 1 个偏维护：

- `daily-papers`：每日推荐全流程
- `paper-reader`：读单篇论文
- `domain-papers`：按领域和子类别长期整理论文笔记
- `generate-mocs`：手动补刷目录页

另外还有 3 个内部 skill，主要给调试和重跑单步用：

- `daily-papers-fetch`
- `daily-papers-review`
- `daily-papers-notes`

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

默认会。读单篇论文和跑完整的每日推荐流程时，结束后通常都会自动刷新一次。`更新索引` 更像是手动补刷入口。

**不用 Zotero 可以吗？**

可以。每日推荐不依赖 Zotero，单篇阅读也支持直接输入 arXiv 链接或本地 PDF。Zotero 主要用于已有文献库的搜索、归类和批量处理。

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
