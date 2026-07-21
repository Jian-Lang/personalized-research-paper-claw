# Research Paper Noter

论文笔记整理项目，负责两类长期笔记工作流：

- **Personalized 笔记**：您给出一篇或多篇论文后，agent 会调用 `paper-reader` 生成详细笔记，并追加到 `PersonalizedPaperContent.md`。
- **Domain Research Gallery**：按领域和子类别维护 related work，详细笔记写入 `{domain}/paper`，可浏览的领域论文 Gallery 写入 `{domain}/content`。

这个项目不包含每日论文推荐流水线；每日抓取、筛选和推送在 `../daily-conf-paper-delivery`。

## 🖼️ Highlight：Domain Research Gallery

Domain 模式不是论文文件夹，也不只是标题索引。它会把逐篇阅读结果整理成一个持续生长的领域研究画廊：

- `_index.md` 是整个 domain 的入口，连接所有 category 与 subcategory。
- 每个 category Gallery 按年份和发布日期组织论文，展示首图、一句话总结、双语摘要、问题背景、核心方法、评估与借鉴意义。
- 每项新工作都会带有“与其他工作的关系”，说明它对已有工作的继承、对比或互补，而不是成为一篇孤立笔记。
- Gallery 条目通过 Obsidian 双链连接完整论文笔记；自动区块可重复更新、排序与去重，页面中的手写内容会保留。

```text
{markdown_root}/DomainPapers/{domain}/
├── paper/
│   └── {paper_note}.md
└── content/
    ├── _index.md
    └── {category_path}.md
```

## 🚀 使用

```bash
./bin/paper-read.sh "Paper title or arXiv URL"
./bin/paper-read.sh "Title 1" "Title 2"
./bin/paper-read.sh /path/to/titles.txt
```

加入 Domain Research Gallery：

添加论文时，`Domain` 和 `Category` 都是必填项。以 `MLLM Personalization` 为例，`Category` 可以是单级的 `Personalized Understanding`，也可以用 `/` 或 `>` 写成多级路径，例如 `Personalized Understanding / Long-Context Personalization`。自然语言输入缺少其中一项时，Skill 只追问缺少项，并保留已经提供的分类与论文。

```bash
./bin/domain-paper-add.sh \
  "MLLM Personalization" \
  "Personalized Understanding / Long-Context Personalization" \
  "TAMEing Long Contexts in Personalization: Towards Training-Free and State-Aware MLLM Personalized Assistant"
```

同一条命令可以继续传入多篇论文或一个标题文件。Noter 会生成或复用详细笔记，再更新对应 category Gallery 与 domain 索引。

## 🗂️ 目录

```text
research-paper-noter/
├── bin/
│   ├── paper-read.sh
│   └── domain-paper-add.sh
├── obsidian-templates/
└── skills/
    ├── _shared/
    ├── manual-papers/
    ├── domain-papers/
    ├── paper-reader/
    └── generate-mocs/
```

## ⚙️ 配置

所有笔记共用仓库根目录 `config/user-config.local.json` 中的 `paths.markdown_root`。如果尚未配置：

```bash
cp config/user-config.example.json config/user-config.local.json
```

Personalized 和 Domain 目录会在各自第一次运行时自动创建，不需要提前准备。Zotero 是可选输入源；需要时再复制本项目的可选配置：

```bash
cp research-paper-noter/skills/_shared/user-config.example.json \
  research-paper-noter/skills/_shared/user-config.local.json
```

这个 Noter 专属配置只保存 Zotero 路径、索引刷新和 git 行为，不会重复配置 Markdown 根目录。

强烈推荐用 Obsidian 打开 `markdown_root`：选择“Open folder as vault / 打开文件夹作为仓库”即可阅读全部 Markdown、双向链接和 Gallery。Obsidian Sync 可选。

## 🔒 默认行为

默认会自动刷新论文目录页，但不会自动 commit 或 push。是否启用 git 自动化由 Noter 配置里的 `automation.git_commit` 和 `automation.git_push` 控制。
