---
name: paper-reader
description: |
  Use when user asks to "read paper", "analyze paper", "summarize paper",
  "读论文", "分析文献", "帮我看一下这篇paper", "论文笔记", or provides a PDF file
  that appears to be an academic paper. Specialized for CV/DL papers.

  Also supports Zotero integration: "读一下这篇论文 ...", "快速看一下这篇论文 ...",
  "批判性分析这篇论文 ...", "读一下 Zotero 里的 XXX", "批量读一下 Zotero 里 VLA 分类下的论文"

  **重要触发词**: "读一下 XXX"、"读一下这篇"、"帮我读" → 必须调用此 skill
---

> **开始前**: 先跟用户打个招呼 🐕

# 学术论文阅读助手 (Paper Reader)

专注 CV/DL 领域，支持 Zotero 集成和 Obsidian 笔记保存。

## Step 0: 读取共享配置

先通过 `../_shared/user_config.py` 读取配置。所有笔记路径都从仓库根目录 `config/user-config.local.json` 中的全局 Markdown 根目录派生；索引与 git 开关来自 Noter 专属配置，未配置字段回退到代码默认值。

显式生成并在后续统一使用这些变量：

- `VAULT_PATH`
- `DAILY_PROJECT_PATH`
- `DAILY_MOCS_PATH`
- `DAILY_NOTES_PATH`
- `MANUAL_PROJECT_PATH`
- `MANUAL_MOCS_PATH`
- `MANUAL_NOTES_PATH`
- `DOMAIN_VAULT_PATH`
- `DOMAIN_PAPERS_PATH`（仅当当前调用来自 `domain-papers` 时使用）
- `TARGET_NOTES_PATH`
- `ZOTERO_DB`
- `ZOTERO_STORAGE`
- `AUTO_REFRESH_INDEXES`
- `GIT_COMMIT_ENABLED`
- `GIT_PUSH_ENABLED`

其中：

- `DAILY_PROJECT_PATH = {VAULT_PATH}/{daily_papers_folder}`
- `DAILY_MOCS_PATH = {DAILY_PROJECT_PATH}/{project_mocs_folder}`
- `DAILY_NOTES_PATH = {DAILY_PROJECT_PATH}/{project_papers_folder}`
- `MANUAL_PROJECT_PATH = {VAULT_PATH}/{manual_papers_folder}`
- `MANUAL_MOCS_PATH = {MANUAL_PROJECT_PATH}/{project_mocs_folder}`
- `MANUAL_NOTES_PATH = {MANUAL_PROJECT_PATH}/{project_papers_folder}`
- `DOMAIN_VAULT_PATH = {VAULT_PATH}/DomainPapers`，仅用于 domain-papers 项目
- `TARGET_NOTES_PATH` 的选择规则：
  - 如果当前调用来自 `daily-papers-notes` / 每日推荐流水线，使用 `DAILY_NOTES_PATH`
  - 如果当前调用来自 `domain-papers`，使用调用方显式给出的 `DOMAIN_PAPERS_PATH`
  - 其他情况默认使用 `MANUAL_NOTES_PATH`
- `GIT_PUSH_ENABLED` 只有在 `GIT_COMMIT_ENABLED=true` 时才可能为真

后续统一使用上面的变量。写入前确保当前 `TARGET_NOTES_PATH` 存在；只创建当前调用方对应的项目目录。

## 1. 接收论文

| 输入方式 | 示例 | 处理方法 |
|----------|------|----------|
| PDF 路径 | `/path/to/paper.pdf` | 直接 Read |
| arXiv 链接 | `https://arxiv.org/abs/xxxx` | WebFetch |
| Zotero 分类 | "VLA 分类的论文" | 查询数据库 → 列出 → 用户选择 |
| Zotero 搜索 | "Zotero 里的 π0.5" | 搜索标题 → 找到 PDF |
| 无 PDF | Zotero 条目无附件 | 从网上获取（见下方） |

### 无 PDF 时的获取流程

1. `python3 assets/zotero_helper.py info {item_id}` 获取论文信息
2. 按优先级获取：arXiv HTML > arXiv PDF > DOI > WebSearch 标题
3. 判断 arXiv ID：从 URL / Zotero extra 字段 / 标题搜索
4. 推荐直接 WebFetch `https://arxiv.org/html/{arxiv_id}`，无需下载
5. 跳过条件：既无 PDF 也无在线来源 / 非论文内容

> Zotero 详细操作见 `references/zotero-guide.md`

## 2. 阅读模式

| 模式 | 触发词 | 输出 |
|------|--------|------|
| **快速摘要** | "快速看一下"、"quick" | 3-5 句核心贡献 |
| **完整解析** | "详细分析"、默认 | 结构化笔记（用模板） |
| **批判分析** | "批判性分析"、"critique" | 方法论优缺点评估 |
| **知识提取** | "提取公式"、"技术细节" | 公式 + 算法伪代码 |

## 3. 笔记生成

**模板**: 严格遵循 `assets/paper-note-template.md`，不可自行简化。

### 核心质量规则

1. **零遗漏**: 论文中所有 Figure、所有 Table 必须全部出现在笔记中；公式只保留理解方法必要的关键公式
2. **术语标注**: 正文中首次出现的重要技术术语可以用 `[[术语]]` 链接，但不要额外创建派生概念笔记
3. **严禁 ASCII 流程图**: 用结构化 Markdown 列表 + `$数学符号$` 描述架构
4. **公式完整性**: 每个公式必须有名称、LaTeX 公式、含义、符号说明；可使用 `[[术语|名称]]` 链接
5. **摘要层级**: `## 一句话总结` 后单独开启 `## 论文摘要` section，再写 `- **论文摘要 / English**:` 和 `- **论文摘要 / 中文**:`；摘要不能作为“一句话总结”的子内容。英文为原始 abstract，中文为忠实翻译，不加工总结
6. **关键图固定位置**: 如果论文有 intro / teaser / motivation / overview 图，必须在 `## 一句话总结` 下方立即重复嵌入；如果论文有 framework / architecture / method overview / pipeline 图，必须在 `## 方法详解` 下方立即重复嵌入。两张图仍然要在 `## 关键图表` 中按 Figure 编号完整出现
7. **禁用 HTML 公式索引**: 不要输出 `### HTML 公式索引`，不要粘贴 arXiv HTML / LaTeXML 抽取出的编号数学片段列表
8. **图片外链优先**: arXiv HTML / 项目主页 / GitHub，找不到再本地下载

> 公式/图片/表格的详细质量规范见 `references/quality-standards.md`

### 图片获取流程（多源 fallback）

**目标**: 确保笔记中包含论文的**所有 Figure**，先统计论文 Figure 总数再逐一获取。

1. WebSearch `"{论文标题} arxiv"` 获取 arXiv ID
2. **来源 A — arXiv HTML**（首选）：
   - WebFetch `https://arxiv.org/html/{arxiv_id}` 提取所有 `<figure>` 的标题与 img src URL
   - 统计论文 Figure 总数，确认提取数量是否完整
3. **来源 B — 项目主页**（HTML 404 或图片不全时）：
   - 从摘要/HTML 中查找项目主页 URL（常见模式：`project page`、`github.io`、`our website`）
   - WebFetch 项目主页，提取展示图片（通常包含 teaser / demo 图）
4. **来源 C — PDF 提取**（前两者都失败时）：
   - `pdfimages -png` 从 PDF 中提取，筛选 >10KB 的有效图片
5. 笔记中用 `![Figure X](url)` 外链嵌入
6. 验证：外链可加载 / 本地文件 >10KB
7. **URL 去重**：写入前检查 URL 中是否有重复的 arxiv_id 路径段（如 `2603.05312v1/2603.05312v1/`），有则删除重复段。详见 `references/image-troubleshooting.md`

> ar5iv 编号不一定对应 Figure 编号，排错见 `references/image-troubleshooting.md`

### 图片可靠性保障（生成后自动执行）

笔记保存后，运行图片可达性检查脚本，自动将不可访问的外链图片下载到本地：
```bash
python3 assets/download_note_images.py "{笔记完整路径}"
```
- 可达的外链保持不动，不可达的自动下载到 `assets/` 并替换为 Obsidian wikilink
- 如有本地化操作，frontmatter `image_source` 自动更新为 `mixed`

### 公式格式

每个公式必须包含：名称、LaTeX `$$` 块（前后留空行）、含义、符号列表。
`$$` 块前后**必须有空行**否则 Obsidian 不渲染。超长公式用 `aligned` 拆分。
只写关键公式，不写 `HTML 公式索引` 或从 HTML 自动抽取的零散公式列表。

## 4. Obsidian 保存

### 文件命名

只用**方法名/模型名**：`{方法名}.md`（如 `Pi05.md`，不加年份前缀）。
方法名判断：标题冒号前 / Abstract 中 "We propose XXX" / 希腊字母转 ASCII。
不确定时保存到 `_inbox/`。

### 保存路径

保存到 `{TARGET_NOTES_PATH}`。

- Zotero 批量阅读可以继续按 Zotero 分类层级：`{TARGET_NOTES_PATH}/{zotero_collection_path}/{方法名}.md`
- `domain-papers` 调用时直接保存到 `{DOMAIN_PAPERS_PATH}/{方法名}.md`，不要落到 daily/manual 目录，也不要按 Zotero 分类拆子目录

### YAML frontmatter

```yaml
---
title: "论文标题"
method_name: "MethodName"
authors: [Author1, Author2]
year: 2025
venue: arXiv
tags: [tag1, tag2]  # 小写连字符，3-8 个
zotero_collection: 3-Robotics/1-VLX/VLA
image_source: online
created: YYYY-MM-DD
---
```

Tags 判断：看 Related Work 小标题 + Abstract 关键词。第一个 tag 是最核心主题。

### 保存后自动执行

1. 只有在 `AUTO_REFRESH_INDEXES=true` 时才刷新目录页：
   ```bash
   python3 ../_shared/generate_paper_mocs.py
   ```
2. 只有在 `GIT_COMMIT_ENABLED=true` 时才做 git：
   - 先确认 `VAULT_PATH/.git` 存在
   - `git add {新增文件} {daily_papers_folder}/ {manual_papers_folder}/` 后必须真的有 staged changes
   - 满足条件后再执行：
   ```bash
   cd {VAULT_PATH} && git add {新增文件} {daily_papers_folder}/ {manual_papers_folder}/ && git commit -m "add paper note: {方法名}"
   ```
   - 只有在 `GIT_PUSH_ENABLED=true` 且仓库已配置远端时才 push

## 5. 完成后自检（合并 checklist）

- [ ] 所有 Figure 都在笔记中（数量与论文一致）？
- [ ] 如有 intro / teaser 图，是否已出现在 `## 一句话总结` 下方？
- [ ] 如有 framework / architecture / pipeline 图，是否已出现在 `## 方法详解` 下方？
- [ ] 关键公式都在笔记中（变量一致、无冲突，未粘贴 HTML 公式索引）？
- [ ] 所有 Table 完整保留（所有行列）？
- [ ] 图片可用（外链可加载 / 本地 >10KB）？

## 6. 交互式功能

完成解析后询问：深入解释？对比其他论文？保存到 Obsidian？

## 7. 批量处理

支持 Zotero 分类批量处理（默认递归子分类）。流程：递归获取论文 → 去重 → 跳过已有笔记 → 依次处理 → 汇总。

## 参考文件（按需查阅）

- **`references/zotero-guide.md`** — Zotero 查询、分类、PDF 路径获取、智能分类判断
- **`references/image-troubleshooting.md`** — ar5iv 图片编号对应、PDF 提取备选
- **`references/quality-standards.md`** — 公式/图片/表格的详细质量规范 + 自检清单
