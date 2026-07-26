[English](README.md) · **简体中文**

# Research Paper Noter

论文笔记整理项目，负责两类长期笔记工作流：

- **Personalized 笔记**：您给出一篇或多篇论文后，agent 会调用 `paper-reader` 生成详细笔记，并追加到 `PersonalizedPaperContent.md`。
- **Domain Research Gallery**：按领域和子类别维护 related work，生成详细的单论文笔记与领域概览页，并可按需导出便于分享的 Gallery HTML 阅读页。

这个项目不包含每日论文推荐流水线；每日抓取、筛选和推送在 `../daily-conf-paper-delivery`。

## 🖼️ Highlight：Domain Research Gallery

Domain 模式不是论文文件夹，也不只是标题索引。它会把逐篇阅读结果整理成一个持续生长的领域研究画廊：

- `_index.md` 是整个 domain 的入口，连接所有 category 与 subcategory。
- 每个 category Gallery 按年份和发布日期组织论文，展示首图、一句话总结、双语摘要、问题背景、核心方法、评估与借鉴意义。
- 每项新工作都会带有“与其他工作的关系”，说明它对已有工作的继承、对比或互补，而不是成为一篇孤立笔记。
- Gallery 条目通过 Obsidian 双链连接完整论文笔记；自动区块可重复更新、排序与去重，页面中的手写内容会保留。
- 整个 domain 或指定子领域可以一键导出为响应式静态 HTML，无需 Obsidian 即可直接打开、托管和分享。

```text
{markdown_root}/DomainPapers/{domain}/
├── paper/
│   └── {paper_note}.md
├── content/
│   ├── _index.md
│   └── {category_path}.md
└── html/                       # 明确要求导出后才创建
    ├── index.html              # 整个 domain
    └── {category_slug}.html    # 指定子领域
```

## 🚀 使用

```bash
./bin/paper-read.sh "Paper title or arXiv URL"
./bin/paper-read.sh "Title 1" "Title 2"
./bin/paper-read.sh /path/to/titles.txt
```

加入 Domain Research Gallery：

添加论文时，`Domain` 和 `Category` 都是必填项。以 `MLLM Personalization` 为例，`Category` 可以是单级的 `Personalized Understanding`，也可以用 `/` 或 `>` 写成多级路径，例如 `Personalized Understanding / Long-Context Personalization`。

```bash
./bin/domain-paper-add.sh \
  "MLLM Personalization" \
  "Personalized Understanding / Long-Context Personalization" \
  "TAMEing Long Contexts in Personalization: Towards Training-Free and State-Aware MLLM Personalized Assistant"
```

同一条命令可以继续传入多篇论文或一个标题文件。Noter 会生成或复用详细笔记，再更新对应 category Gallery 与 domain 索引。

### ♻️ 批量重建 category Galleries

当 domain 内的论文集合、category 或基础元信息经过批量调整后，可以批量重建该 domain 下的全部 category Galleries，也可以只重建一个子领域：

```text
重新生成 Recommendation Systems domain 下的全部 category Galleries
重新生成 Recommendation Systems domain 下 LLM-based Recommendation 子领域的 Gallery
```

也可以直接运行脚本：

```bash
# 从当前论文笔记重建 domain 下的全部 category Galleries
./bin/domain-paper-gallery-rebuild.sh "Recommendation Systems"

# 只重建指定子领域
./bin/domain-paper-gallery-rebuild.sh \
  "Recommendation Systems" \
  "LLM-based Recommendation"
```

首次添加论文必须提供 `domain + category`，用于确定论文所属的内层 Gallery；重建时省略 category，表示批量处理笔记中已经记录好的全部 category。脚本以当前 `paper/*.md` 确认论文集合、分类与基础元信息，同时保留 sidecar 中已经整理好的 Gallery 摘要、工作关系和页面手写内容，再刷新自动区块与 domain 索引。它不会创建外层聚合 Gallery，也不会重新生成论文笔记、导出 HTML、commit 或 push；正常添加论文时不会自动触发批量重建。

### 🌐 按需导出 Gallery HTML

当 Gallery 已经整理完成，可以直接对 Codex 说：

```text
导出 Recommendation Systems domain 的 HTML
导出 Recommendation Systems domain 的 LLM-based Recommendation 子领域 HTML
```

只提供 domain 时，所有 category/subcategory 会合并到同一页面；继续提供 category 路径时，只导出指定子领域。多级子领域沿用 `/`，例如 `Personalized Understanding / Long-Context Personalization`。

也可以直接运行脚本：

```bash
# 合并导出整个 domain
./bin/domain-paper-gallery-html.sh "Recommendation Systems"

# 只导出指定子领域
./bin/domain-paper-gallery-html.sh \
  "Recommendation Systems" \
  "LLM-based Recommendation"
```

HTML 默认写入 `{markdown_root}/DomainPapers/{domain}/html/`。正常添加 domain 论文时不会自动导出 HTML；导出也不会修改已有笔记、content Gallery 或索引。

## 🗂️ 目录

```text
research-paper-noter/
├── bin/
│   ├── paper-read.sh
│   ├── domain-paper-add.sh
│   ├── domain-paper-gallery-rebuild.sh
│   └── domain-paper-gallery-html.sh
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
