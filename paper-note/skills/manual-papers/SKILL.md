---
name: manual-papers
description: |
  手动论文阅读流程。用户提供一个或多个论文标题 / arXiv 链接 / DOI / 标题文件时使用。
  逐篇调用 paper-reader 生成完整详细笔记，并把论文追加到一个累计汇总 Markdown。

  触发词："手动论文阅读"、"读这些论文"、"paper-read.sh"、"把这些论文加入阅读汇总"
---

# 手动论文阅读

这是用户主动提供论文后的累计阅读流程。它和每日推荐流程共享详细笔记模板，但汇总页是独立的长期累计文件。

## Step 0: 读取共享配置

先读取 `../_shared/user-config.local.json`。未配置的字段回退到代码内置默认值。

显式生成并在后续统一使用这些变量：

- `VAULT_PATH`
- `MANUAL_PROJECT_PATH`
- `MANUAL_MOCS_PATH`
- `MANUAL_NOTES_PATH`
- `MANUAL_SUMMARY_PATH`
- `AUTO_REFRESH_INDEXES`
- `GIT_COMMIT_ENABLED`
- `GIT_PUSH_ENABLED`

其中：

- `MANUAL_PROJECT_PATH = {VAULT_PATH}/{manual_papers_folder}`；如果配置中没有 `manual_papers_folder`，使用 `PersonalizedPaper`
- `MANUAL_MOCS_PATH = {MANUAL_PROJECT_PATH}/{project_mocs_folder}`
- `MANUAL_NOTES_PATH = {MANUAL_PROJECT_PATH}/{project_papers_folder}`
- `MANUAL_SUMMARY_PATH = {MANUAL_MOCS_PATH}/PersonalizedPaperContent.md`
- `GIT_PUSH_ENABLED` 只有在 `GIT_COMMIT_ENABLED=true` 时才可能为真

后续统一使用上面的变量。

## 输入

用户会提供一个或多个论文标题、arXiv 链接、DOI、PDF 路径，或一个包含多行标题/链接的文本文件。

处理规则：

1. 如果输入是文件路径，逐行读取；跳过空行和以 `#` 开头的注释行。
2. 如果输入是多个命令行参数，每个参数视为一篇论文标题或链接。
3. 每篇论文独立处理；不要因为其中一篇失败而跳过其他论文。

## Step 1: 解析论文来源

对每篇论文按优先级找到可读来源：

1. arXiv 链接：直接使用 `https://arxiv.org/abs/{id}`，并优先读 `https://arxiv.org/html/{id}`。
2. DOI：使用 DOI 页面，并搜索 arXiv 版本。
3. PDF 路径：直接作为本地论文来源。
4. 纯标题：WebSearch `"{论文标题}" arxiv`，优先选择标题精确匹配的 arXiv 结果；找不到再搜索 DOI / project page。

如果无法确认来源，记录失败原因，继续处理下一篇。

## Step 2: 生成详细笔记

每篇论文必须调用 `paper-reader` skill 生成完整详细笔记。

要求：

- 详细笔记格式严格复用 `paper-reader/assets/paper-note-template.md`
- `## 一句话总结` 和 `## 论文摘要` 必须是同级 section
- 如果论文有 intro / teaser / motivation / overview 图，详细笔记必须在 `## 一句话总结` 下方立即重复嵌入
- 如果论文有 framework / architecture / method overview / pipeline 图，详细笔记必须在 `## 方法详解` 下方立即重复嵌入
- 不创建概念笔记，不刷新概念 MOC
- 生成后执行 paper-reader 自己定义的图片可靠性检查和质量自检
- 如果已有同一论文的合格详细笔记，复用已有笔记，不重复生成

## Step 3: 更新累计汇总

汇总文件是长期累计文件：

`{MANUAL_SUMMARY_PATH}`

如果目录或文件不存在，创建：

```markdown
```

### 汇总页结构

汇总页只包含按主题组织的论文条目。

主题使用一级标题：

```markdown
# {主题名}
```

论文条目使用二级标题：

```markdown
## {序号}. {论文标题}
- **加入日期**: YYYY-MM-DD
- **笔记**: [[方法名]]
- **年份**: YYYY
- **Venue**: arXiv / CVPR / ICCV / NeurIPS / ...
- **链接**: [arXiv](...) / [PDF](...) / [Code](...)
![[{project_papers_folder}/assets/{首图文件名}|600]]
- **一句话总结**: ...
- **论文摘要 / English**: 原始 abstract 原文，禁止改写
- **论文摘要 / 中文**: 上一行 English 摘要的忠实中文翻译
- **问题背景**: ...
- **核心方法**: ...
- **评估**: ...
- **借鉴意义**: ...
```

要求：

- 每个主题内的论文条目都要显式编号，从 `1.` 开始递增
- 每篇论文条目都要显式写出论文年份和 venue；优先从详细笔记 frontmatter 的 `year` / `venue` 读取
- 每篇论文条目都要插入一张首图；优先使用对应详细笔记已下载/已生成的本地首图资源
- 如果已有多张图，优先选 teaser / framework / overview 这一类最适合作为内容封面的图

### 主题归类规则

每加入一篇论文时，先读取现有汇总中的 `#` 主题标题。

1. 根据论文标题、abstract、方法、任务和详细笔记 tags 判断主题。
2. 如果能自然归入已有主题，就把新论文条目追加到该主题末尾、下一个 `##` 主题之前。
3. 如果现有主题都不合适，才在文件末尾创建新的 `## {主题名}`，并把论文放进去。
4. 主题粒度由论文内容决定，不等同于关键词列表；不要机械地把每个 keyword 变成一个主题。

### 追加约束

更新汇总时必须保持最小改动：

- 只新增本次论文条目，必要时只新增一个新的 `##` 主题标题
- 不重写已有论文条目
- 不改写已有主题名
- 不调整已有主题顺序
- 不重新排序旧论文
- 不改已有正文措辞

如果检测到同一论文已经在汇总里（arXiv ID、标题或笔记 wikilink 匹配），不要重复追加；只在最终报告中说明已存在。

## Step 4: 刷新索引

只有在 `AUTO_REFRESH_INDEXES=true` 时刷新论文目录页：

```bash
python3 ../_shared/generate_paper_mocs.py
```

不刷新概念目录页。

## Step 5: Git 自动化

仅当 `GIT_COMMIT_ENABLED=true` 时执行，并且必须先检查：

1. `VAULT_PATH/.git` 存在
2. `git add -A` 后确实有 staged changes

满足条件后才 commit：

```bash
cd {VAULT_PATH} && git add -A && git commit -m "manual papers: YYYY-MM-DD"
```

只有在 `GIT_PUSH_ENABLED=true` 且仓库已配置远端时才 push。

## 输出

完成后告知用户：

- 成功生成或复用详细笔记多少篇
- 追加到汇总多少篇
- 新建了哪些主题
- 跳过了哪些已存在论文或失败论文
