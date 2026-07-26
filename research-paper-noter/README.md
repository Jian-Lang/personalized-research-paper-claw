**English** · [简体中文](README.zh-CN.md)

# Research Paper Noter

The paper-note organization subproject. It supports two long-term workflows:

- **Personalized notes**: after you provide one or more papers, the agent calls `paper-reader` to create detailed notes and appends them to `PersonalizedPaperContent.md`.
- **Domain Research Gallery**: maintains related work by domain and subcategory, creates detailed single-paper notes and field overview pages, and exports share-ready Gallery HTML on demand.

This subproject does not contain the daily recommendation pipeline. Daily fetching, filtering, and delivery live in `../daily-conf-paper-delivery`.

## 🖼️ Highlight: Domain Research Gallery

Domain mode is not a paper folder or a title-only index. It turns paper-by-paper reading into a field map designed to keep growing:

- `_index.md` is the domain entry point and connects all categories and subcategories.
- Each category Gallery organizes papers by year and publication date, showing a teaser figure, one-sentence summary, bilingual abstract, problem background, core method, evaluation, and takeaways.
- Every new work includes “Relationships to other work,” explaining its inheritance, contrast, or complementarity instead of leaving it as an isolated note.
- Obsidian wikilinks connect Gallery entries to complete paper notes. Generated blocks can be updated, sorted, and deduplicated repeatedly while handwritten page content is preserved.
- An entire domain or one subfield can be exported as responsive static HTML that opens, hosts, and shares without Obsidian.

```text
{markdown_root}/DomainPapers/{domain}/
├── paper/
│   └── {paper_note}.md
├── content/
│   ├── _index.md
│   └── {category_path}.md
└── html/                       # Created only after an explicit export
    ├── index.html              # Entire domain
    └── {category_slug}.html    # One subfield
```

## 🚀 Usage

Create Personalized notes:

```bash
./bin/paper-read.sh "Paper title or arXiv URL"
./bin/paper-read.sh "Title 1" "Title 2"
./bin/paper-read.sh /path/to/titles.txt
```

Add a paper to a Domain Research Gallery:

Both `Domain` and `Category` are required. For example, under `MLLM Personalization`, `Category` can contain one level such as `Personalized Understanding`, or multiple levels separated by `/` or `>`, such as `Personalized Understanding / Long-Context Personalization`.

```bash
./bin/domain-paper-add.sh \
  "MLLM Personalization" \
  "Personalized Understanding / Long-Context Personalization" \
  "TAMEing Long Contexts in Personalization: Towards Training-Free and State-Aware MLLM Personalized Assistant"
```

The same command can accept additional papers or a title file. Noter creates or reuses detailed notes, then updates the corresponding category Gallery and domain index.

### ♻️ Rebuild Category Galleries After Bulk Changes

After bulk changes to a domain’s paper collection, categories, or base metadata, rebuild every category Gallery in the domain or just one subfield:

```text
Rebuild all category Galleries under the Recommendation Systems domain.
Rebuild the LLM-based Recommendation Gallery under the Recommendation Systems domain.
```

You can also run the scripts directly:

```bash
# Rebuild every category Gallery in the domain from current paper notes.
./bin/domain-paper-gallery-rebuild.sh "Recommendation Systems"

# Rebuild only one subfield.
./bin/domain-paper-gallery-rebuild.sh \
  "Recommendation Systems" \
  "LLM-based Recommendation"
```

Adding a paper for the first time requires `domain + category` to identify its inner Gallery. Omitting category during rebuild means processing every category already recorded in the notes. The script uses current `paper/*.md` files to confirm the paper collection, classification, and base metadata while preserving curated Gallery summaries, paper relationships, and handwritten page content stored in sidecars. It refreshes generated blocks and the domain index.

Rebuilding does not create an outer aggregate Gallery, regenerate paper notes, export HTML, commit, or push. Normal paper addition never triggers a bulk rebuild automatically.

### 🌐 Export Gallery HTML on Demand

Once a Gallery is ready, tell Codex:

```text
Export the Recommendation Systems domain as HTML.
Export the LLM-based Recommendation subfield of Recommendation Systems as HTML.
```

With only a domain, all categories and subcategories are merged into one page. Add a category path to export one subfield. Multi-level paths continue to use `/`, for example `Personalized Understanding / Long-Context Personalization`.

Direct script usage:

```bash
# Merge and export the entire domain.
./bin/domain-paper-gallery-html.sh "Recommendation Systems"

# Export only one subfield.
./bin/domain-paper-gallery-html.sh \
  "Recommendation Systems" \
  "LLM-based Recommendation"
```

HTML is written to `{markdown_root}/DomainPapers/{domain}/html/` by default. Adding a domain paper never exports HTML automatically. Exporting also leaves existing notes, content Galleries, and indexes unchanged.

## 🗂️ Directory Layout

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

## ⚙️ Configuration

All notes share `paths.markdown_root` from the repository-level `config/user-config.local.json`. If it is not configured yet:

```bash
cp config/user-config.example.json config/user-config.local.json
```

Personalized and Domain directories are created on their respective first runs. Zotero is an optional input source. When needed, copy this subproject’s optional configuration:

```bash
cp research-paper-noter/skills/_shared/user-config.example.json \
  research-paper-noter/skills/_shared/user-config.local.json
```

The Noter-specific configuration stores only Zotero paths, index-refresh behavior, and git behavior. It does not duplicate the Markdown root setting.

Obsidian is strongly recommended. Choose **Open folder as vault** and open `markdown_root` to read all Markdown, wikilinks, and Galleries. Obsidian Sync is optional.

## 🔒 Default Behavior

Paper index pages refresh automatically by default, while automatic commit and push remain disabled. Enable git automation only through `automation.git_commit` and `automation.git_push` in the Noter configuration.
