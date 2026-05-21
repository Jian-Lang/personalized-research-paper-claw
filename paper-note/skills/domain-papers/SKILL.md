---
name: domain-papers
description: |
  Domain-specific paper note workflow. Use when the user provides one or more papers plus a domain
  and category/subcategory, and wants notes saved into a separate domain Obsidian vault with
  domain/{paper,content} structure. Reuses paper-reader/manual note style, supports incremental
  additions, and updates content pages sorted by paper year.

  触发词："domain论文"、"领域论文整理"、"加入domain"、"domain-paper-add.sh"
---

# Domain Paper Notes

这个 skill 是第三套独立论文项目。它复用 `paper-reader` 的详细笔记模板和 `manual-papers` 的 content 条目风格，但写入新的 domain vault，不改 daily/manual 项目。

## Step 0: 读取配置

先读取 `../_shared/user-config.local.json`。未配置字段回退到代码默认值。

显式生成并统一使用：

- `DOMAIN_VAULT_PATH = paths.domain_papers_vault`
- `DOMAIN_PROJECT_PATH = {DOMAIN_VAULT_PATH}/{domain}`
- `DOMAIN_PAPERS_PATH = {DOMAIN_PROJECT_PATH}/{domain_paper_folder}`，默认 `paper`
- `DOMAIN_CONTENT_PATH = {DOMAIN_PROJECT_PATH}/{domain_content_folder}`，默认 `content`
- `AUTO_REFRESH_INDEXES`
- `GIT_COMMIT_ENABLED`
- `GIT_PUSH_ENABLED`

不要把 domain 论文写入 `DailyPapers` 或 `PersonalizedPaper`。

## 输入

用户提供一篇或多篇论文，并为每篇论文指定：

- `domain`: 顶层领域文件夹，例如 `TTA`
- `category_path`: content 内的大类/子类路径，例如 `multimodal TTA` 或 `test-time adaptation / VLM TTA`
- `paper`: 论文标题、arXiv URL、DOI 或 PDF 路径

如果同一批论文共享同一个 `domain` 和 `category_path`，按批处理。缺少分类时先问用户，不要自行发明分类。

## Step 1: 创建目录

确保下面两个目录存在：

```text
{DOMAIN_PROJECT_PATH}/paper
{DOMAIN_PROJECT_PATH}/content
```

其中 `paper` 存放详细论文笔记，`content` 存放按用户分类维护的汇总页。

## Step 2: 生成或复用详细笔记

每篇论文调用 `paper-reader` 生成详细笔记，格式严格复用 `paper-reader/assets/paper-note-template.md`。

调用约束：

- 当前调用来源是 `domain-papers`
- `TARGET_NOTES_PATH` 必须设为 `{DOMAIN_PAPERS_PATH}`
- 笔记直接保存到 `{DOMAIN_PAPERS_PATH}`，不要按 Zotero 分类或 daily/manual 路径保存
- 如果论文有 intro / teaser / motivation / overview 图，详细笔记必须在 `## 一句话总结` 下方立即重复嵌入
- 如果论文有 framework / architecture / method overview / pipeline 图，详细笔记必须在 `## 方法详解` 下方立即重复嵌入
- 如果已有同一论文的合格详细笔记，复用已有笔记，不重复生成
- 生成后执行 paper-reader 自己定义的质量检查和图片可靠性检查

文件命名沿用 `paper-reader` 的方法名/模型名规则，例如 `Tent.md`、`CoTTA.md`。

## Step 3: 更新 content

生成或复用笔记后，运行 domain content 更新脚本：

```bash
python3 skills/domain-papers/scripts/update_domain_content.py \
  --domain "{domain}" \
  --category-path "{category_path}" \
  --title "{paper_title}" \
  --note "{note_name}" \
  --year "{paper_year}" \
  --published-date "{paper_published_date}" \
  --url "{paper_url}" \
  --venue "{venue}" \
  --summary "{one_sentence_summary}" \
  --abstract-en "{original_abstract}" \
  --abstract-zh "{faithful_abstract_translation}" \
  --background "{model_written_background}" \
  --method "{model_written_method}" \
  --evaluation "{model_written_evaluation}" \
  --significance "{model_written_significance}" \
  --related-work "{relation_to_new_batch_or_existing_domain_papers}" \
  --figure "{first_figure_markdown}"
```

规则：

- content 文件位置是 `{DOMAIN_CONTENT_PATH}/{category_path}.md`
- 脚本只更新自动管理区块，保留用户在 content 页其他位置手写的内容
- 同一 content 子类内按 `year` 从新到旧排序；同一年内，arXiv 论文按 `published_date` 从新到旧排序，非 arXiv 或缺少完整日期的论文按标题排序
- 同一论文用标题去重；重复添加时更新已有条目
- 论文条目复用 manual content 风格：编号、加入日期、笔记双链、年份、Venue、论文链接、首图、一句话总结、英文/中文摘要、问题背景、核心方法、评估和借鉴意义
- 年份和 Venue 是 content 条目的必填基础信息；优先从详细笔记 frontmatter 的 `year` / `venue` 读取，其次使用脚本参数
- `论文摘要 / English` 直接使用原始 abstract，禁止改写；`论文摘要 / 中文` 是忠实翻译
- `问题背景`、`核心方法`、`评估`、`借鉴意义` 必须由当前 agent 基于详细笔记二次整理，保持 manual-papers 的 content 写法；不要把详细笔记 section 机械截取进 content
- 批处理最后生成 content 时，只对本次新增论文补充 `--related-work`；用几句话说明它与本批新增论文或同 domain 已有论文的承接、对比、互补关系。已在 content 中存在且本次未新增的旧论文不需要回填这一段
- `update_domain_content.py` 只负责排序、去重和落盘；如果没有传入二次整理字段，才允许退回到从详细笔记抽取作为兜底

## Step 4: 可选 Git

只有在 `GIT_COMMIT_ENABLED=true` 时才执行，并且必须先检查：

1. `{DOMAIN_VAULT_PATH}/.git` 存在
2. `git add -A` 后确实有 staged changes

满足条件后才 commit：

```bash
cd {DOMAIN_VAULT_PATH} && git add -A && git commit -m "domain papers: {domain} YYYY-MM-DD"
```

只有在 `GIT_PUSH_ENABLED=true` 且仓库已配置远端时才 push。

## 输出

完成后告知用户：

- 成功生成或复用详细笔记多少篇
- 更新了哪些 domain/category content 页
- 哪些论文已存在、失败或缺少年份
- domain vault 的实际写入路径
