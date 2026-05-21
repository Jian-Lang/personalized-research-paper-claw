# Obsidian Daily Paper Deployment

This deployment stores all generated content in the Obsidian vault configured by
`RESEARCH_PAPER_CLAW_VAULT_DIR` or by `skills/_shared/user-config.local.json`.

```text
~/ObsidianVault
```

The project-managed structure inside the vault is:

```text
Obsidian Vault/
├── DailyPapers/
└── PaperNotes/
    └── _inbox/
```

The active config is `skills/_shared/user-config.local.json`. It keeps the
repository skill format and workflow, and points `paths.obsidian_vault` at your
Obsidian vault.

## Manual Run

```bash
./bin/daily-paper-recommend.sh
```

The daily recommendation file is written to:

```text
~/ObsidianVault/DailyPapers/mocs/DailyPaperContent-YYYY-MM-DD.md
```

Logs are written to `logs/`.

The script runs Codex non-interactively with `danger-full-access` and
`ask-for-approval=never` so the unattended job can fetch HF/arXiv data and write
to the Obsidian vault. The prompt is fixed to the repository `daily-papers` skill
entrypoint.

## Schedule

The launchd plist in `launchd/` is a template. Replace
`/ABSOLUTE/PATH/TO/Research-Paper-Claw` with your local checkout path before
installing it. It runs the same script every day at 08:00 local time.

```bash
cp launchd/com.example.research-paper-claw.daily-paper-recommend.plist ~/Library/LaunchAgents/
launchctl bootstrap "gui/$(id -u)" ~/Library/LaunchAgents/com.example.research-paper-claw.daily-paper-recommend.plist
```
