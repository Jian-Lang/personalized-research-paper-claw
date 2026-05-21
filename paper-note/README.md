# paper-note

论文笔记整理项目，负责两类长期笔记工作流：

- **Personalized 笔记**：用户主动给一篇或多篇论文，由 agent 调用 `paper-reader` 生成详细笔记，并追加到 `PersonalizedPaperContent.md`。
- **Domain 笔记**：按领域和子类别维护 related work，详细笔记写入 `{domain}/paper`，分类汇总写入 `{domain}/content`。

这个项目不包含每日论文推荐流水线；每日抓取、筛选和推送在 `../daily-paper`。

## 使用

```bash
./bin/paper-read.sh "Paper title or arXiv URL"
./bin/paper-read.sh "Title 1" "Title 2"
./bin/paper-read.sh /path/to/titles.txt
```

```bash
./bin/domain-paper-add.sh "TTA" "multimodal TTA" "Paper title or arXiv URL"
./bin/domain-paper-add.sh "TTA" "VLM TTA" "Title 1" "Title 2"
./bin/domain-paper-add.sh "TTA" "multimodal TTA" /path/to/titles.txt
```

## 目录

```text
paper-note/
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

## 配置

配置文件是 `skills/_shared/user-config.local.json`，如果不存在会使用代码内置默认值。首次使用建议从示例复制一份：

```bash
cp skills/_shared/user-config.example.json skills/_shared/user-config.local.json
```

主要路径包括：

- `paths.obsidian_vault`
- `paths.manual_papers_folder`
- `paths.domain_papers_vault`
- `paths.domain_paper_folder`
- `paths.domain_content_folder`
- `paths.zotero_db`
- `paths.zotero_storage`

## 默认行为

默认会自动刷新论文目录页，但不会自动 commit 或 push。是否启用 git 自动化由配置里的 `automation.git_commit` 和 `automation.git_push` 控制。
