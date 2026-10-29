# User configuration / 用户配置

These JSON files are active defaults, ready to use and edit directly. No copying or renaming is required. All paths are relative to the repository root.

这些 JSON 是运行时直接读取的默认配置，可以灵活修改，无需复制或改名。所有路径均相对于仓库根目录。

| File / 文件 | Settings / 设置 |
| --- | --- |
| [user-config.json](user-config.json) | Shared Markdown root and folder layout / 共享 Markdown 根目录、目录布局 |
| [delivery-config.json](delivery-config.json) | Conferences, quotas, scoring, review profile, Daily automation / 会议、每天篇数、关键词、点评、Daily 定时与自动化 |
| [noter-config.json](noter-config.json) | Zotero paths and Noter automation / Zotero 路径、Noter 索引与 git 自动化 |

For example, set `paths.markdown_root` in `user-config.json`, then edit `daily_papers.conferences[].daily_take`, `topics`, and `keywords` in `delivery-config.json`. EMNLP 2026 is bundled, with a default daily maximum of 5 papers; `shuffle: true` mixes main-conference papers and Findings at import time. The quota is a maximum: fewer papers are returned when not enough match your interests.

例如，先在 `user-config.json` 修改 `paths.markdown_root`，再到 `delivery-config.json` 设置会议的 `daily_take`、`topics` 和 `keywords`。仓库已包含 EMNLP 2026，默认每天最多 5 篇；导入时通过 `shuffle: true` 混合主会与 Findings。配额是上限，符合兴趣的论文不足时会少于这个数量。

## Optional personal overrides / 可选个人覆盖

You may instead put personal settings in `user-config.local.json`, `delivery-config.local.json`, or `noter-config.local.json` here. They are ignored by git. Runtime code recursively merges each default with its matching local file; local values win, and arrays replace the entire default array. Shared `paths` apply to both workflows, and each workflow keeps its own automation settings. Restart a long-running Python process after editing its configuration.

也可以在本目录使用上述三个同名的 `*.local.json` 保存个人设置，它们已被 git 忽略。读取顺序为代码兜底 → 默认 JSON → 对应的个人覆盖 JSON，逐层合并对象，个人值优先；数组整体替换。共享 `paths` 对两个功能生效，各功能的 automation 相互独立。修改配置后重新运行命令即可生效；长期运行的 Python 进程需要重启。

For example, this `delivery-config.local.json` changes only the recommendation threshold while inheriting all other defaults:

```json
{
  "daily_papers": {
    "min_score": 3
  }
}
```

Changing a schedule time requires rerunning `daily-conf-paper-delivery/bin/configure-schedule.sh` to update launchd. Changing interests or quotas takes effect on the next uncached recommendation run; an existing recommendation cache for the same date is reused. Neither configuration files nor cloning the repository enable scheduling automatically.

修改定时时间后需重新运行 `daily-conf-paper-delivery/bin/configure-schedule.sh` 才会更新 launchd。兴趣和配额对下一次未缓存的推荐生效，同一天已生成的缓存会复用。clone 或修改配置不会自动启用定时任务。
