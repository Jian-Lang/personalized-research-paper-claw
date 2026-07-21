# Daily Conf Paper Delivery: Local Scheduling

Daily Conf Paper Delivery can run immediately on demand or automatically once a day. Cloning the repository never starts either mode. Scheduling is optional, must be installed explicitly, and currently uses macOS launchd.

The recommended interface is natural language through the `daily-papers` skill:

```text
每天早上 8 点推荐论文
把每日推荐改到 09:30
查看每日推荐定时状态
关闭每日论文推荐
```

The commands below are the lower-level interface for troubleshooting or non-conversational environments.

## Manual Run

Manual runs start immediately and do not wait for the configured schedule:

```bash
cd daily-conf-paper-delivery
./bin/daily-conf-paper-delivery.sh
```

The recommendation page is written to:

```text
{markdown_root}/DailyPapers/mocs/DailyPaperContent-YYYY-MM-DD.md
```

Runtime logs are written to `daily-conf-paper-delivery/logs/`.

## Configure Daily Time

Set and install the schedule in one command using 24-hour `HH:MM` format:

```bash
./bin/configure-schedule.sh --time 08:00
```

The value uses the Mac's current local timezone. Check the loaded task with:

```bash
./bin/configure-schedule.sh --status
```

The script also passes the root-level `paths.markdown_root` to the scheduled runner. After changing the Markdown root, run `./bin/configure-schedule.sh` again. To change the time, rerun it with `--time HH:MM`.

Remove the task with:

```bash
./bin/configure-schedule.sh --remove
```

## Behavior

- `daily_run_time` affects only the installed launchd task.
- Natural-language and manual shell runs always start immediately.
- The scheduled task runs the same `daily-conf-paper-delivery.sh` entrypoint.
- Index refresh follows `automation.auto_refresh_indexes`.
- Git commit and push remain disabled unless explicitly enabled.

The unattended runner uses Codex without interactive approval prompts and should only be installed on a trusted personal machine.
