# Research Paper Noter Architecture

`research-paper-noter` 只负责论文笔记整理，不负责每日论文推荐。

## Workflows

```text
用户提供论文
    │
    ├─ Personalized 笔记 ──→ manual-papers
    │                         ├─ 调用 paper-reader 生成或复用详细笔记
    │                         ├─ 追加 PersonalizedPaperContent.md
    │                         └─ 可选刷新论文目录页
    │
    └─ Domain 笔记 ────────→ domain-papers
                              ├─ 调用 paper-reader 写入 {domain}/paper
                              ├─ update_domain_content.py 构建 category Gallery
                              ├─ 记录新工作与已有工作的关系
                              └─ 更新 domain 索引，按年份和发布日期排序、去重
```

## Skills

- `manual-papers`: personalized 论文阅读汇总入口。
- `domain-papers`: domain related work 笔记入口。
- `paper-reader`: 单篇论文详细笔记生成器，支持 arXiv、本地 PDF、Zotero。
- `generate-mocs`: 刷新论文目录页。
- `_shared`: 配置加载和 MOC 构建公共代码。

## Shared Utilities

`paper-reader/assets/download_note_images.py` 负责检查笔记里的外链图片。可访问的外链保持不动，不可访问的图片会下载到本地 `assets/` 并替换为 Obsidian wikilink。

`domain-papers/scripts/update_domain_content.py` 负责 Domain Research Gallery 的自动管理区块：将首图、摘要、方法、评估、借鉴意义和 `related_work` 渲染到 category 页，完成排序、去重与落盘，并保留用户手写内容。每次更新还会重建 `content/_index.md`，作为整个 domain 的 Gallery 入口。

## Storage

Personalized 默认写入：

```text
{markdown_root}/PersonalizedPaper/
├── mocs/PersonalizedPaperContent.md
└── papers/
```

Domain 默认写入：

```text
{markdown_root}/DomainPapers/{domain}/
├── paper/                  # 完整论文笔记
└── content/
    ├── _index.md           # Domain Research Gallery 入口
    └── {category_path}.md  # Category Gallery
```
