**English** · [简体中文](README.zh-CN.md)

# Daily Conf Paper Delivery

The daily paper recommendation subproject. It filters papers from local conference acceptance lists, creates a recommendation page, and writes the result as Markdown under the global notes root.

> 📺 [Early pipeline demo video](http://xhslink.com/o/1dhQCn40EWY) — this shows an earlier version of the same workflow.

## Latest Changes

- Recommendation quotas are now configured explicitly with `daily_take` inside each entry of `daily_papers.conferences`.
- ACL 2026 is included. The default sources are ICML 2026, ICLR 2026, CVPR 2026, and ACL 2026.
- Conference proportions follow each conference entry’s `daily_take`; change that value to adjust the mix.
- ACL enables `shuffle: true` by default. Importing local acceptance lists performs a stable random mix of posters and Findings, avoiding a sequence in which all main-conference papers appear before Findings.

## 🦴 What It Does

- Collects a batch of new papers, performs an initial relevance pass, and creates a recommendation list.
- Controls conference sources and proportions through `daily_papers.conferences` and their `daily_take` values.
- Scores title + abstract using topic / keyword preferences and preserves match reasons, conference source, list order, paper links, PDF links, and other metadata.
- Writes the recommendation page into the Obsidian-compatible notes directory and maintains index / navigation pages.
- Optionally creates detailed notes for recommended papers.

The output is organized approximately as follows:

```text
ResearchNotes/
└── DailyPapers/
    ├── mocs/DailyPaperContent-YYYY-MM-DD.md
    └── papers/.../*.md
```

Template:

- [Obsidian note template](obsidian-templates/论文笔记模板.md)

## 🐕 Usage

For a one-time recommendation, tell Codex:

```text
Recommend today's papers.
Recommend papers from the past 3 days.
Recommend papers from the past week.
```

Scheduling also uses natural language:

```text
Recommend papers every day at 8:00 a.m.
Move the daily recommendation to 09:30.
Show the daily recommendation schedule.
Disable daily paper recommendations.
```

On macOS, the `daily-papers` Skill installs, updates, checks, or removes the scheduled task. You do not need to run scheduler scripts manually. “Recommend today’s papers” performs one run and does not change schedule state.

To read one paper or maintain Personalized / Domain collections, use the sibling `../research-paper-noter` subproject.

Index pages normally refresh automatically. If you manually changed the layout or suspect the index is stale, say:

```text
Refresh the paper index.
```

## 🏡 Installation

Requirements:

- Codex CLI
- [Obsidian](https://obsidian.md/) (strongly recommended, but not a runtime dependency)
- [Python 3.8+](https://www.python.org/)
- [`poppler-utils`](https://poppler.freedesktop.org/) (`apt install poppler-utils` / `brew install poppler`)
- [Zotero](https://www.zotero.org/) (optional)

Git version control is recommended for the Obsidian vault. A history becomes increasingly valuable as the note collection grows and also helps with multi-device synchronization.

Run the following from the repository root. Symbolic links ensure that Skills always read configuration, scripts, and conference data from the current checkout, and allow natural-language schedule management to locate the scheduler accurately:

```bash
SKILLS_DIR="${CODEX_HOME:-$HOME/.codex}/skills"
mkdir -p "$SKILLS_DIR"

ln -s "$PWD/daily-conf-paper-delivery/skills/_shared" "$SKILLS_DIR/_shared"
ln -s "$PWD/daily-conf-paper-delivery/skills/daily-papers" "$SKILLS_DIR/daily-papers"
ln -s "$PWD/daily-conf-paper-delivery/skills/daily-papers-fetch" "$SKILLS_DIR/daily-papers-fetch"
ln -s "$PWD/daily-conf-paper-delivery/skills/daily-papers-review" "$SKILLS_DIR/daily-papers-review"
ln -s "$PWD/daily-conf-paper-delivery/skills/daily-papers-notes" "$SKILLS_DIR/daily-papers-notes"
ln -s "$PWD/daily-conf-paper-delivery/skills/paper-reader" "$SKILLS_DIR/paper-reader"
ln -s "$PWD/daily-conf-paper-delivery/skills/generate-mocs" "$SKILLS_DIR/generate-mocs"

# Configure the global Markdown root once at the repository root.
cp config/user-config.example.json config/user-config.local.json

# The Daily subproject stores only conferences and research preferences.
cp daily-conf-paper-delivery/skills/_shared/user-config.example.json \
  daily-conf-paper-delivery/skills/_shared/user-config.local.json
```

Set `paths.markdown_root` in the root `config/user-config.local.json`. The first run creates `DailyPapers/mocs` and `DailyPapers/papers`; no manual `mkdir` is required.

## ⚙️ Configuration

The global Markdown root lives in the repository-level `config/user-config.local.json`. This directory’s `skills/_shared/user-config.local.json` contains only Daily-specific settings. Edit it directly or tell Codex how you want it changed.

Copy `skills/_shared/user-config.example.json` for first-time setup. Runtime code reads only `user-config.local.json`.

Primary settings:

| Setting | Description |
| --- | --- |
| `daily_papers.conferences` | Conference, year, and per-conference quota entries, for example `[{ "name": "ICML", "year": 2026, "daily_take": 5 }, { "name": "ICLR", "year": 2026, "daily_take": 5 }, { "name": "CVPR", "year": 2026, "daily_take": 5 }, { "name": "ACL", "year": 2026, "daily_take": 5, "shuffle": true }]`; local files are matched using `<CONF>/<conf>_<year>.jsonl` |
| `daily_papers.conferences[].daily_take` | Maximum papers recommended from that conference each day; this is the current conference-mix control |
| `daily_papers.conferences[].shuffle` | Whether to apply stable random mixing when importing a local list; enabled for ACL to mix posters and Findings |
| `daily_papers.daily_take` | Legacy global fallback; new configurations should prefer per-conference values |
| `daily_papers.scan_limit` | Maximum entries scanned after the current cursor for each conference; defaults to 1000 and stops even when `daily_take` is not filled |
| `daily_papers.topics` | Research areas and review-page categories; a full title or abstract match scores +1 |
| `daily_papers.keywords` | Specific method names and synonymous expressions; a full title match scores +3, otherwise an abstract match scores +1 |
| `daily_papers.exclude_keywords` | Exclusions; a full title or abstract match scores -100 |
| `daily_papers.min_score` | Recommendation threshold; defaults to 2, so a topic-only match is insufficient |
| `automation.auto_refresh_indexes` | Refresh index pages after the current workflow; never starts a recommendation by itself |
| `automation.git_commit` | Commit automatically after completion; disabled by default |
| `automation.git_push` | Push after an automatic commit; disabled by default |
| `automation.daily_run_time` | Automatic daily time on macOS in 24-hour `HH:MM` format; defaults to `08:00` |

Configure conference proportions directly here:

```json
"conferences": [
  { "name": "ICML", "year": 2026, "daily_take": 5 },
  { "name": "ICLR", "year": 2026, "daily_take": 5 },
  { "name": "CVPR", "year": 2026, "daily_take": 5 },
  { "name": "ACL", "year": 2026, "daily_take": 5, "shuffle": true }
]
```

Zotero configuration is used only by later detailed-note generation and is unnecessary for Daily recommendations alone.

## 🦮 Default Behavior

Obsidian-vault git automation is disabled by default:

- `auto_refresh_indexes = true`
- `git_commit = false`
- `git_push = false`
- `daily_run_time = "08:00"`

These settings describe Daily’s post-run behavior. Index pages refresh by default, but git is untouched and the presence of configuration does not start recommendations. `daily_run_time` takes effect only after a scheduled task is installed; manual requests run immediately. If your Obsidian vault already uses git and you want automatic commits, enable `git_commit` explicitly.

## 🐾 Pipeline Overview

**Daily recommendation** reads local AI-conference JSONL and creates a single daily page in two stages:

1. **Fetch and filter**: a Python script reads `conferences` and matches bundled acceptance lists using `data/paperlist/<CONF>/<conf>_<year>.jsonl`. The repository currently includes ICML, ICLR, CVPR, and ACL. Every conference maintains its own cursor. `shuffle: true` performs stable random mixing only during import. A full topic match in title or abstract scores +1; a full keyword match in title scores +3, otherwise a full abstract match scores +1; an exclusion match scores -100. Case and punctuation are normalized, matching respects complete word or phrase boundaries, and duplicates count once. Papers must reach `min_score`. For each conference, the pipeline recommends at most its own `daily_take` and scans at most `scan_limit` entries after the cursor.
2. **Summarize and review**: Codex reads candidates and their `score_breakdown`, applies the same `topics` for reading triage and grouping, and creates a summary note for every paper. Notes contain metadata, bilingual abstracts, background, motivation, method, evaluation, takeaways, and a concise critique. All recommendations are collected in one page under `DailyPapers/`, while `.history.json` is updated. Page frontmatter topics and keywords come directly from the configuration.

Curated acceptance-list updates will be provided for important new conferences. Updating the repository makes new bundled data available.

To maintain a conference or journal from another field, place compatible JSONL at `data/paperlist/<CONF>/<conf>_<year>.jsonl`. Every line must contain at least `title` and `abstract`, and the source must be listed in `daily_papers.conferences`. If you already have local data with the same layout, run:

```bash
python3 scripts/sync_paperlist.py --source-dir /path/to/local/paperlist
```

The script copies only configured conference JSONL from the local directory you specify. Daily recommendation itself does not depend on an external paper-list repository.

Fine-grained paper notes are not generated by default. Run the optional paper-notes stage or use `../research-paper-noter` when detailed notes are needed.

`generate-mocs` maintains index pages by recursively scanning paper notes and concept-library directories and generating wikilink-based navigation.

See [ARCHITECTURE.md](ARCHITECTURE.md) for implementation details.

## 🏠 Repository Contents

The complete Daily workflow is the normal entry point. Other Skills mainly support debugging, optional notes, and index maintenance:

- `daily-papers`: complete Daily recommendation workflow
- `daily-papers-fetch`: filtering, scoring, and deduplication
- `daily-papers-review`: summary review and recommendation page
- `daily-papers-notes`: optional detailed notes
- `paper-reader`: detailed notes for recommended papers
- `generate-mocs`: manual index refresh

## 🎾 Advanced Usage

To run one pipeline stage independently, say:

```text
Run paper fetching.
Run paper review.
Run paper notes.
```

For troubleshooting or direct scheduler management without Codex:

```bash
./bin/configure-schedule.sh --time 08:00
./bin/configure-schedule.sh --status
./bin/configure-schedule.sh --remove
```

Automatic scheduling currently supports macOS launchd and uses local system time. The low-level scripts are not required for normal operation.

## 🐶 FAQ

**Can the complete workflow run from one request?**

Yes. Say `Recommend today's papers`. The default flow chains fetching and abstract-based review. Detailed paper notes are an optional third stage and do not run automatically.

**Do index pages refresh automatically?**

Yes, by default. The complete Daily workflow and the paper-notes stage normally refresh them after completion. `Refresh the paper index` is a manual recovery entry point.

**Can I use it without Zotero?**

Yes. Daily recommendations do not depend on Zotero. Zotero is mainly used for later detailed notes and searching an existing library.

**Can I use it without Obsidian?**

Yes. Outputs are ordinary Markdown files. Obsidian is strongly recommended: select **Open folder as vault** and open the configured `markdown_root`. No notes or Obsidian Sync subscription need to exist beforehand.

**Can it assist with paper writing?**

Yes. It is useful for organizing related work, maintaining a note library, and creating reading outlines. Verify AI-generated content before using it.

**Does it modify my git repository by default?**

No. `commit / push` are disabled unless you explicitly enable them.

## ⚠️ Disclaimer

This tool comes from a real research workflow. AI-generated recommendations, reviews, and notes may contain factual errors or omissions. Treat it as a research assistant, not a replacement for your judgment.

Bugs and platform-specific issues may occur. When you encounter a small problem, asking an AI coding agent to diagnose it alongside you is often the fastest path.

## License

Apache-2.0. See `LICENSE`.
