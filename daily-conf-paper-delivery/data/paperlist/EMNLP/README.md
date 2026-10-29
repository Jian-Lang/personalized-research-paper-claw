# EMNLP 2026 snapshot

- Source: [`ronpay/paperlist`, commit `2abfb696da9e2b1508615d6217ab830beb01087a`](https://github.com/ronpay/paperlist/tree/2abfb696da9e2b1508615d6217ab830beb01087a/EMNLP).
- Imported on 2026-10-29 from `EMNLP/emnlp_2026.jsonl`.
- 5,182 papers: 2,704 main-conference papers (`poster`) and 2,478 Findings (`finding`). All rows contain title, authors, abstract, Anthology page, and PDF links.
- Upstream SHA-256: `3644883a9a0f60f3fa221f4765ba520220bdd165718066268ea2a9ba9c2972ad`.
- Bundled SHA-256: `0bf5f6440dcf062a371e563f30bf31c8c4be987b7add87666b211256cf872f99`.

Only row ordering changes: the existing importer applies stable random mixing with `shuffle: true`, so main-conference papers and Findings can both appear from the start. Each record is unchanged. Presentation status follows the upstream labels; `poster` does not identify actual oral/poster assignments.

Upstream metadata comes from the ACL Anthology's `2026.emnlp-main` and `2026.findings-emnlp` volumes. The upstream repository includes GPL-2.0; its license is preserved in [LICENSE.paperlist](LICENSE.paperlist).

Configure this source in the root `config/delivery-config.json` (or its optional local override):

```json
{"name": "EMNLP", "year": 2026, "daily_take": 5, "shuffle": true}
```

`daily_take` is the daily maximum, subject to topic/keyword filtering. This source starts with its own cursor; adding it does not reset other conference progress.
