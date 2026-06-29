# research-paper-claw

research-paper-claw is a Codex-powered research paper workflow toolkit for discovering, reading, organizing, and maintaining paper notes in Obsidian.

The project currently packages two working systems:

- `daily-paper-recommender`: conference-paper discovery and daily recommendation pages.
- `paper-note`: single-paper reading, personalized paper notes, domain paper collections, and Obsidian content pages.

The long-term direction is one project with multiple services: recommendation, paper reading, domain knowledge base maintenance, and index generation.

## Features

- Daily paper recommendations from configured conference sources.
- Keyword-based filtering with positive and negative preferences.
- Summary-style recommendation pages for Obsidian.
- Full paper notes from arXiv links, paper titles, local PDFs, or Zotero entries.
- Domain-specific paper collections with `{domain}/paper` and `{domain}/content` structure.
- Automatic content-page updates with note links, abstracts, figures, and structured summaries.
- Obsidian MOC/index generation.
- Optional local automation through shell scripts and launchd examples.

## Repository Layout

```text
Research-Paper-Claw/
├── README.md
├── LICENSE
├── daily-paper-recommender/
│   ├── bin/
│   ├── skills/
│   ├── obsidian-templates/
│   ├── launchd/
│   ├── README.md
│   └── ARCHITECTURE.md
└── paper-note/
    ├── bin/
    ├── skills/
    ├── obsidian-templates/
    ├── README.md
    └── ARCHITECTURE.md
```

## Quick Start

Install the skills you want to use into your Codex skills directory.

```bash
mkdir -p ~/.codex/skills
cp -r daily-paper-recommender/skills/* ~/.codex/skills/
cp -r paper-note/skills/* ~/.codex/skills/
```

Create local config files from the examples, then edit the paths and keywords:

```bash
cp daily-paper-recommender/skills/_shared/user-config.example.json \
  daily-paper-recommender/skills/_shared/user-config.local.json

cp paper-note/skills/_shared/user-config.example.json \
  paper-note/skills/_shared/user-config.local.json
```

Common settings for `daily-paper-recommender` include:

- `paths.obsidian_vault`
- `paths.zotero_db`
- `paths.zotero_storage`
- `daily_papers.conferences`
- `daily_papers.conferences[].daily_take`
- `daily_papers.conference_preferences.keywords`
- `daily_papers.conference_preferences.negative_keywords`

Common settings for `paper-note` include:

- `paths.obsidian_vault`
- `paths.manual_papers_folder`
- `paths.domain_papers_vault`
- `paths.domain_paper_folder`
- `paths.domain_content_folder`
- `paths.zotero_db`
- `paths.zotero_storage`
- `automation.auto_refresh_indexes`

The tools also have built-in defaults, so skills can start without a local config file. In real use, create `user-config.local.json`; local config files are ignored by git because they contain machine-specific paths.

## Main Commands

Daily recommendations:

```bash
cd daily-paper-recommender
./bin/daily-paper-recommend.sh
```

Read or add individual papers:

```bash
cd paper-note
./bin/paper-read.sh "Paper title or arXiv URL"
```

Maintain a domain-specific paper collection:

```bash
cd paper-note
./bin/domain-paper-add.sh "TTA" "multimodal TTA" "Paper title or arXiv URL"
./bin/domain-paper-add.sh "TTA" "VLM TTA" "Title 1" "Title 2"
./bin/domain-paper-add.sh "TTA" "multimodal TTA" /path/to/titles.txt
```

## Workflows

### Daily Recommendations

`daily-paper-recommender` reads configured conference paper-list snapshots, filters papers by title and abstract, generates a daily recommendation page, and writes it into the configured Obsidian vault.

Current conference snapshots include ICML 2026, ICLR 2026, CVPR 2026, and ACL 2026. Each configured conference has its own `daily_take`, so recommendation mix is controlled directly in `daily_papers.conferences`. See `daily-paper-recommender/README.md` for details.

### Paper Notes

`paper-note` uses the `paper-reader` skill to generate structured paper notes from paper titles, arXiv links, local PDFs, or Zotero entries. It handles paper metadata, figures, formulas, tables, and Obsidian-friendly markdown.

### Domain Paper Collections

`paper-note` also supports long-running domain collections. Detailed notes are written to:

```text
{domain_papers_vault}/{domain}/paper
```

Content pages are written to:

```text
{domain_papers_vault}/{domain}/content
```

The content updater keeps entries sorted by year, deduplicates by paper title, and stores structured metadata in `.domain-papers.json`.

## Requirements

- Codex CLI
- Python 3.8+
- Obsidian
- Zotero, optional
- Poppler, recommended for PDF image extraction

On macOS:

```bash
brew install poppler
```

## Open Source Notes

This repository intentionally ignores runtime outputs and local machine state:

- `logs/`
- `state/`
- local config files
- generated Obsidian vault copies
- Python caches

Before publishing to GitHub, check that no private Obsidian paths, Zotero database paths, generated logs, or personal paper states are staged.

## License

Apache License 2.0. See `LICENSE`.
