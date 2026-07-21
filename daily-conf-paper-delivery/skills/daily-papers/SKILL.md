---
name: daily-papers
description: |
  Daily 推荐配置、每日论文推荐与定时管理的一句话总入口。收到“初始化 Daily 推荐配置”“创建 Daily 配置文件”
  时创建或更新本地偏好配置；收到“今日论文推荐”“过去3天论文推荐”“过去一周论文推荐”
  “最近3天论文”“看看这周有啥论文”时运行单次推荐；收到“每天早上8点推荐论文”“开启每日论文推荐”
  “修改每日推荐时间”“查看定时推荐状态”“关闭每日论文推荐”时管理本地定时任务。

  单次推荐自动串联会议论文抓取、摘要式推荐生成两步；定时管理在 macOS 上通过 launchd 完成。
---

# 每日论文推荐

这是面向用户的一句话入口。对用户来说，正常只需要说一次：

- `今日论文推荐`
- `过去3天论文推荐`
- `过去一周论文推荐`
- `初始化 Daily 推荐配置，我关注 Recommendation Systems 和 LLM-based Recommendation`
- `每天早上 8 点推荐论文`
- `把每日推荐改到 09:30`
- `查看每日推荐定时状态`
- `关闭每日论文推荐`

## 先判断意图

1. 如果请求初始化或创建 Daily 推荐配置，进入“初始化 Daily 配置”并在完成后停止。
2. 如果请求开启、修改、查看或关闭定时推荐，进入“定时管理”并在完成后停止，不要同时运行论文推荐。
3. 如果请求今日、最近几天或过去一周的论文，进入“单次推荐”。
4. 如果只询问如何配置或开启定时推荐，只解释自然语言用法，不修改文件或系统状态。

## 初始化 Daily 配置

从当前 Skill 的真实路径定位 `../_shared/user-config.example.json` 和 `../_shared/user-config.local.json`。

- 如果没有 local 文件，以 example 为结构创建；如果已经存在，只更新本次明确提供的字段，不覆盖整个文件。
- 从请求中提取研究方向写入 `daily_papers.topics`，提取重点词写入 `daily_papers.keywords`，提取排除方向写入 `daily_papers.exclude_keywords`。
- 只提供研究方向时，为每个 topic 补充简洁、明确的常用关键词或同义表达，并在完成时列出实际写入内容。
- 不要沿用 example 中示范性质的 topics、keywords 或 exclude keywords；保留默认 conferences、`min_score` 和 automation 设置。
- 如果请求没有提供任何研究方向，先询问关注方向，不要生成带示例偏好的 local 文件。
- 使用 JSON 解析与序列化更新配置，保证结果是有效 JSON。
- 创建或更新配置后，报告文件位置和核心偏好；除非请求同时明确要求推荐，否则不要启动论文流程。

## 定时管理

优先从当前 Skill 的真实路径定位 `../../bin/configure-schedule.sh`，不要依赖当前工作目录。如果 Skill 是复制安装且该相对路径不存在，只在当前项目中查找 `daily-conf-paper-delivery/bin/configure-schedule.sh`；仍找不到时，提示改用 README 推荐的符号链接安装，不要猜测路径。调度属于显式开启的本地系统行为；clone 仓库或安装 Skill 都不得自动注册任务。

- 开启或更新时间：把自然语言时间规范化为 24 小时制 `HH:MM`，执行 `configure-schedule.sh --time HH:MM`。没有明确时间时，沿用 Daily 配置中的 `automation.daily_run_time`。
- 查看状态：执行 `configure-schedule.sh --status`。
- 关闭定时：执行 `configure-schedule.sh --remove`。
- 开启、更新或关闭后，再执行一次 `configure-schedule.sh --status` 核验最终状态。
- 只有请求本身明确表达开启、更新或关闭时才修改系统状态；环境要求授权时，正常请求授权。
- 如果根级或 Daily 本地配置尚未建立，停止并引导完成配置，不要从 example 偷偷创建一套偏好。
- 当前只支持 macOS launchd；其他系统明确说明尚未支持，不要模拟成功。
- 定时管理不会立即补跑一次推荐。完成后告诉用户当前是启用还是关闭、每日时间，以及下一次会在何时触发。

## 单次推荐

## 执行原则

执行流水线前，先通过 `../_shared/user_config.py` 读取仓库根目录 `config/user-config.local.json` 中的全局 Markdown 根目录，并运行 `ensure_daily_layout()`。第一次使用时只创建 `DailyPapers/mocs` 与 `DailyPapers/papers`。

1. 先识别时间范围：
   - `今日论文推荐`、`每日推荐`、`今日论文` -> 当天
   - `过去3天论文推荐`、`最近3天论文` -> 3 天
   - `过去一周论文推荐`、`看看这周有啥论文` -> 7 天
2. 自动调用 `daily-papers-fetch` skill。
3. 第 1 步完成后，自动调用 `daily-papers-review` skill。
4. 不自动调用 `daily-papers-notes` skill。当前会议推荐只生成摘要式推荐页；只有候选数据里有 `pdf`、`paper_url`、arXiv 或 OpenReview 链接，并且用户明确要求读论文时，才进入 paper-reader。
5. 全部完成后，用一句话告诉用户：
   - 推荐文件已生成
   - 目录页是否已自动刷新

## 重要约束

- 不要先要求用户手动跑 `跑一下论文抓取 / 点评 / 笔记`。
- 这 3 句是内部流水线和调试入口，不是首页主交互。
- 如果用户明确只想跑其中一步，再交给对应 skill。
- `跑一下论文笔记` 只作为手动入口，不属于每日会议推荐默认流程。

## 运行语义

- 本 Skill 是一步运行完整推荐与管理定时任务的统一入口。
- 手动触发“今日论文推荐”时立即运行一次，不等待 `daily_run_time`，也不改变定时状态。
- 定时任务触发时仍运行同一句“今日论文推荐”，不要写死三条内部命令。
