---
name: generate-mocs
description: |
  重新生成 Obsidian 里两个 project 的论文目录页 / 导航页（MOC）。
  当用户说“更新索引”“更新论文目录”“刷新论文目录”“刷新MOC”时使用。
---

# 更新目录页

这个 skill 用于手动补刷 Obsidian 里的目录页 / 导航页（MOC）。

## Step 0: 读取共享配置

先通过 `../_shared/user_config.py` 读取配置：Markdown 根目录来自根级全局配置，索引与 git 开关来自 Daily 专属配置。只刷新已经存在的项目目录，不为了生成索引创建尚未使用的 Daily 或 Personalized 项目。

显式生成并在后续统一使用这些变量：

- `VAULT_PATH`
- `DAILY_PROJECT_PATH`
- `MANUAL_PROJECT_PATH`
- `AUTO_REFRESH_INDEXES`
- `GIT_COMMIT_ENABLED`
- `GIT_PUSH_ENABLED`

其中：

- `DAILY_PROJECT_PATH = {VAULT_PATH}/{daily_papers_folder}`
- `MANUAL_PROJECT_PATH = {VAULT_PATH}/{manual_papers_folder}`
- `GIT_PUSH_ENABLED` 只有在 `GIT_COMMIT_ENABLED=true` 时才可能为真

后续步骤统一使用上面的变量。

## 执行步骤

1. 运行论文目录页脚本：

```bash
python3 ../_shared/generate_paper_mocs.py
```

2. 汇报：
   - 扫描了多少个目录
   - 新建 / 更新了多少个目录页
   - 目录页文件写到了哪里

## git 自动化

默认配置下：

- `AUTO_REFRESH_INDEXES=true`
- `GIT_COMMIT_ENABLED=false`
- `GIT_PUSH_ENABLED=false`

只有在 `GIT_COMMIT_ENABLED=true` 时才做 git 操作，并且必须先检查：

1. `VAULT_PATH/.git` 是否存在
2. `git add` 之后是否真的有 staged changes

只有在上面两项都满足时才 commit。

只有在 `GIT_PUSH_ENABLED=true` 且仓库已配置远端时才 push。

## 结果要求

- 目录页生成逻辑必须来自仓库自带论文目录脚本，不依赖 `VAULT_PATH/scripts/*`
- 重复运行应保持幂等
- 用户手动运行这个 skill 时，不受 `AUTO_REFRESH_INDEXES` 开关影响
