#!/usr/bin/env python3
"""
Paper Reading Daemon - 后台论文阅读守护进程

功能：
1. 从 Zotero 获取指定分类的论文列表（递归子分类）
2. 调用 Codex 逐篇处理
3. 遇到 rate limit 时自动等待并重试
4. 支持断点续传

用法：
    # 启动守护进程处理 VLA 分类
    screen -S paper-daemon
    python3 paper_daemon.py -c "VLA"

    # 查看进度
    python3 paper_daemon.py --status
"""

import os
import sys
import json
import sqlite3
import shlex
import subprocess
import time
import argparse
import logging
import re
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

_SHARED_DIR = Path(__file__).resolve().parents[1] / "_shared"
if str(_SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(_SHARED_DIR))

from user_config import manual_project_papers_dir, obsidian_vault_path, zotero_db_path, zotero_storage_dir

# 配置
ZOTERO_DB = str(zotero_db_path())
ZOTERO_STORAGE = str(zotero_storage_dir())
OBSIDIAN_VAULT = str(obsidian_vault_path())
PAPER_NOTES_ROOT = str(manual_project_papers_dir())
_DAEMON_STATE_DIR = os.path.expanduser(os.environ.get("PAPER_DAEMON_STATE_DIR", "~/.codex"))
_CODEX_BIN = os.environ.get("PAPER_DAEMON_CODEX_BIN", "codex")
_CODEX_WORKDIR = os.environ.get("PAPER_DAEMON_CODEX_WORKDIR", OBSIDIAN_VAULT)
_CODEX_MODEL = os.environ.get("PAPER_DAEMON_CODEX_MODEL", "").strip()
_CODEX_EXTRA_ARGS = os.environ.get("PAPER_DAEMON_CODEX_ARGS", "")
PROGRESS_FILE = os.path.join(_DAEMON_STATE_DIR, "paper_daemon_progress.json")
LOG_FILE = os.path.join(_DAEMON_STATE_DIR, "paper_daemon.log")
PID_FILE = os.path.join(_DAEMON_STATE_DIR, "paper_daemon.pid")

# Rate limit 配置
INITIAL_WAIT = 60          # 初始等待时间（秒）
MAX_WAIT = 21600           # 最大等待时间（6小时）
WAIT_MULTIPLIER = 2        # 等待时间倍数
BETWEEN_PAPERS_WAIT = 5    # 论文之间的等待时间（秒）
QUOTA_WAIT_TIME = 1800     # 命中配额上限时的默认等待时间（30分钟）

# 设置日志
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

_SUBSCRIPT_TRANSLATION = str.maketrans("₀₁₂₃₄₅₆₇₈₉₊₋", "0123456789+-")
_GREEK_REPLACEMENTS = {
    "π": "pi",
    "ϕ": "phi",
    "φ": "phi",
    "α": "alpha",
    "β": "beta",
    "γ": "gamma",
}


def acquire_lock() -> bool:
    """获取进程锁，防止重复运行"""
    if os.path.exists(PID_FILE):
        with open(PID_FILE, 'r') as f:
            old_pid = f.read().strip()
        # 检查进程是否还在运行
        try:
            os.kill(int(old_pid), 0)
            return False  # 进程还在运行
        except (OSError, ValueError):
            pass  # 进程已结束，可以继续

    # 写入当前 PID
    with open(PID_FILE, 'w') as f:
        f.write(str(os.getpid()))
    return True


def release_lock():
    """释放进程锁"""
    if os.path.exists(PID_FILE):
        os.remove(PID_FILE)


def wait_for_quota_reset(wait_seconds: Optional[int] = None):
    """等待配额重置或人工恢复后再继续。"""
    if wait_seconds is None:
        wait_seconds = QUOTA_WAIT_TIME
    wait_minutes = max(1, wait_seconds // 60)
    logger.info(f"⏳ 配额受限，等待 {wait_minutes} 分钟...")
    time.sleep(wait_seconds)


def detect_limit_error(output: str) -> Optional[str]:
    """识别限额/限速错误类型"""
    text = output.lower()
    if 'rate limit' in text or 'too many requests' in text:
        return 'RATE_LIMIT'
    if 'hit your limit' in text or 'usage limit' in text or 'resets' in text:
        return 'QUOTA_LIMIT'
    return None


def parse_reset_wait_seconds(message: str) -> Optional[int]:
    """
    解析 "resets 9pm (Asia/Shanghai)" 等提示，计算等待秒数
    """
    match = re.search(
        r'resets\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?(?:\s*\(([^)]+)\))?',
        message,
        re.IGNORECASE
    )
    if not match:
        return None

    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    ampm = (match.group(3) or '').lower()
    tz_name = match.group(4) or 'Asia/Shanghai'

    if ampm == 'pm' and hour < 12:
        hour += 12
    if ampm == 'am' and hour == 12:
        hour = 0

    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        return None

    now = datetime.now(tz)
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target = target + timedelta(days=1)

    wait_seconds = int((target - now).total_seconds())
    return max(60, wait_seconds)


def copy_zotero_db() -> str:
    """复制 Zotero 数据库以避免锁定"""
    tmp_db = "/tmp/zotero_readonly.sqlite"
    subprocess.run(["cp", ZOTERO_DB, tmp_db], check=True)
    return tmp_db


def get_collection_id_and_path(db_path: str, collection_name: str) -> tuple[Optional[int], Optional[str]]:
    """根据分类名称获取 ID 和完整路径"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT collectionID, collectionName, parentCollectionID FROM collections")
    collections = {row[0]: {'name': row[1], 'parent': row[2]} for row in cursor.fetchall()}

    def get_path(cid):
        path_parts = []
        current = cid
        while current:
            if current in collections:
                path_parts.insert(0, collections[current]['name'])
                current = collections[current]['parent']
            else:
                break
        return '/'.join(path_parts)

    for cid, info in collections.items():
        if info['name'].lower() == collection_name.lower():
            conn.close()
            return cid, get_path(cid)
        if collection_name.lower() in info['name'].lower():
            conn.close()
            return cid, get_path(cid)

    conn.close()
    return None, None


def get_all_child_collections(db_path: str, collection_id: int) -> list[int]:
    """递归获取所有子分类ID（包含自身）"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT collectionID, parentCollectionID FROM collections")
    all_collections = cursor.fetchall()
    conn.close()

    children_map = {}
    for cid, parent_id in all_collections:
        if parent_id not in children_map:
            children_map[parent_id] = []
        children_map[parent_id].append(cid)

    result = [collection_id]
    def collect_children(cid):
        if cid in children_map:
            for child_id in children_map[cid]:
                result.append(child_id)
                collect_children(child_id)

    collect_children(collection_id)
    return result


def get_papers_in_collection(db_path: str, collection_id: int) -> list[dict]:
    """获取分类下的所有论文（递归包含子分类）"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    collection_ids = get_all_child_collections(db_path, collection_id)
    placeholders = ','.join('?' * len(collection_ids))
    query = f"""
        SELECT DISTINCT i.itemID, idv.value as title
        FROM items i
        JOIN collectionItems ci ON i.itemID = ci.itemID
        JOIN itemData id ON i.itemID = id.itemID
        JOIN itemDataValues idv ON id.valueID = idv.valueID
        JOIN fields f ON id.fieldID = f.fieldID
        WHERE ci.collectionID IN ({placeholders}) AND f.fieldName = 'title' AND i.itemTypeID != 14
    """
    cursor.execute(query, collection_ids)
    logger.info(f"递归查询，包含 {len(collection_ids)} 个分类")

    papers = [{'item_id': row[0], 'title': row[1]} for row in cursor.fetchall()]
    conn.close()
    return papers


def get_pdf_path(db_path: str, item_id: int) -> Optional[str]:
    """获取论文的 PDF 路径"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT ia.path, items.key
        FROM itemAttachments ia
        JOIN items ON ia.itemID = items.itemID
        WHERE ia.parentItemID = ? AND ia.contentType = 'application/pdf'
    """, (item_id,))

    row = cursor.fetchone()
    conn.close()

    if row:
        path, key = row
        if path and path.startswith('storage:'):
            filename = path.replace('storage:', '')
            return os.path.join(ZOTERO_STORAGE, key, filename)
    return None


def get_paper_online_source(db_path: str, item_id: int) -> Optional[dict]:
    """
    获取论文的在线来源信息（arXiv ID、DOI、URL）
    用于处理没有 PDF 的论文
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 获取论文的各种字段
    cursor.execute("""
        SELECT f.fieldName, idv.value
        FROM itemData id
        JOIN fields f ON id.fieldID = f.fieldID
        JOIN itemDataValues idv ON id.valueID = idv.valueID
        WHERE id.itemID = ?
    """, (item_id,))

    fields = {row[0]: row[1] for row in cursor.fetchall()}
    conn.close()

    result = {}

    # 检查 arXiv ID (可能在 extra 字段或 archiveID)
    extra = fields.get('extra', '')
    if 'arXiv:' in extra:
        # 格式: arXiv:2401.12345
        match = re.search(r'arXiv[:\s]+(\d{4}\.\d{4,5})', extra, re.IGNORECASE)
        if match:
            result['arxiv_id'] = match.group(1)

    # 检查 DOI
    doi = fields.get('DOI', '')
    if doi:
        result['doi'] = doi

    # 检查 URL
    url = fields.get('url', '')
    if url:
        result['url'] = url
        # 尝试从 URL 提取 arXiv ID
        if 'arxiv.org' in url and 'arxiv_id' not in result:
            match = re.search(r'arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5})', url)
            if match:
                result['arxiv_id'] = match.group(1)

    return result if result else None


def get_existing_notes() -> dict[str, str]:
    """获取 Obsidian 中已有的笔记（返回 {方法名: 文件路径}）"""
    existing = {}
    notes_dir = Path(PAPER_NOTES_ROOT)
    if notes_dir.exists():
        for md_file in notes_dir.rglob("*.md"):
            name = md_file.stem
            relative_parts = md_file.relative_to(notes_dir).parts
            # 跳过 _inbox, _概念 等特殊目录和目录页
            if any(part.startswith("_") for part in relative_parts):
                continue
            if md_file.parent.name == name:
                continue

            for method_name in _extract_note_method_names(name):
                existing[method_name] = str(md_file)
    return existing


def title_matches_note(title: str, existing_notes: dict[str, str]) -> bool:
    """
    检查论文标题是否与已有笔记匹配
    只有精确匹配方法名时才返回 True
    """
    if not title:
        return False

    normalized_candidates = {
        _normalize_method_name(title.strip()),
        _normalize_method_name(title.split(':', 1)[0].strip()),
    }

    for method_normalized in normalized_candidates:
        if not method_normalized:
            continue
        for note_method in existing_notes.keys():
            # 完全相等
            if note_method == method_normalized:
                return True
            # 笔记方法名完全包含在标题方法名中（且长度相近）
            if note_method in method_normalized and len(note_method) > 3:
                # 确保不是太短的匹配（避免 "gs" 匹配 "3dgs"）
                if len(note_method) >= len(method_normalized) * 0.5:
                    return True

    return False


def _normalize_method_name(value: str) -> str:
    normalized = value.strip().lower().translate(_SUBSCRIPT_TRANSLATION)
    for source, target in _GREEK_REPLACEMENTS.items():
        normalized = normalized.replace(source, target)
    normalized = normalized.replace("&", "and")
    return re.sub(r"[^a-z0-9]+", "", normalized)


def _extract_note_method_names(stem: str) -> set[str]:
    candidates = {stem}

    match = re.match(r"^(?:19|20)\d{2}_(.+)$", stem)
    if match:
        candidates.add(match.group(1))

    return {
        normalized
        for candidate in candidates
        if (normalized := _normalize_method_name(candidate))
    }


def load_progress() -> dict:
    """加载进度"""
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, 'r') as f:
            return json.load(f)
    return {'completed': [], 'failed': [], 'current': None, 'started_at': None}


def save_progress(progress: dict):
    """保存进度"""
    os.makedirs(os.path.dirname(PROGRESS_FILE), exist_ok=True)
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(progress, f, indent=2, ensure_ascii=False)


def call_codex(paper_source: dict, collection_path: str, item_id: int) -> tuple[bool, str]:
    """
    调用 Codex 处理论文

    paper_source 可以包含:
    - pdf_path: 本地 PDF 路径
    - arxiv_id: arXiv ID (如 2401.12345)
    - doi: DOI
    - url: 论文 URL
    - title: 论文标题 (用于搜索)
    """

    arxiv_id = paper_source.get('arxiv_id', '')
    notes_root = PAPER_NOTES_ROOT

    # 构建来源信息
    source_lines = []
    if paper_source.get('pdf_path'):
        source_lines.append(f"PDF 路径: {paper_source['pdf_path']}")
    if arxiv_id:
        source_lines.append(f"arXiv ID: {arxiv_id}")
        source_lines.append(f"arXiv 页面: https://arxiv.org/abs/{arxiv_id}")
        source_lines.append(f"arXiv PDF: https://arxiv.org/pdf/{arxiv_id}.pdf")
        source_lines.append(f"arXiv HTML (图片): https://arxiv.org/html/{arxiv_id}")
    if paper_source.get('doi'):
        source_lines.append(f"DOI: {paper_source['doi']}")
        source_lines.append(f"DOI 链接: https://doi.org/{paper_source['doi']}")
    if paper_source.get('url'):
        source_lines.append(f"URL: {paper_source['url']}")
    if paper_source.get('title'):
        source_lines.append(f"论文标题: {paper_source['title']}")

    source_info = '\n'.join(source_lines)

    # 如果没有 PDF，添加特殊说明
    no_pdf_instruction = ""
    if not paper_source.get('pdf_path'):
        fallback_steps = []
        if arxiv_id:
            fallback_steps.extend(
                [
                    f"1. **arXiv HTML 版本**（推荐）: 用 WebFetch 读取 https://arxiv.org/html/{arxiv_id}，可直接获取图片 URL",
                    f"2. **arXiv 摘要页**: 用 WebFetch 读取 https://arxiv.org/abs/{arxiv_id}",
                    f"3. **arXiv PDF**: 下载 https://arxiv.org/pdf/{arxiv_id}.pdf 到本地后用 Read 读取",
                ]
            )
        if paper_source.get('doi'):
            fallback_steps.append(f"{len(fallback_steps) + 1}. **DOI 页面**: 跳转到 https://doi.org/{paper_source['doi']} 读取")
        if paper_source.get('url'):
            fallback_steps.append(f"{len(fallback_steps) + 1}. **原始 URL**: 读取 {paper_source['url']}")
        if not fallback_steps:
            fallback_steps.append("1. 根据标题搜索在线来源，再优先读取可直接获取图片的 HTML 版本")

        no_pdf_instruction = f"""
## 无本地 PDF - 在线获取（重要）

这篇论文没有本地 PDF，请按以下优先级获取内容：

{chr(10).join(fallback_steps)}

优先使用 HTML 版本，因为可以直接获取在线图片链接！
"""

    prompt = f"""请使用 `paper-reader` skill 读取并分析这篇论文，生成完整的结构化笔记。

{source_info}
Zotero 分类路径: {collection_path}
Zotero ItemID: {item_id}
{no_pdf_instruction}

## 质量要求（重要）

参考高质量笔记风格，必须包含：

1. **元信息表格**: 机构、日期、项目主页、对比基线
2. **中英文摘要**: 在 `## 一句话总结` 后单独开启 `## 论文摘要` section，再写 `- **论文摘要 / English**:` 和 `- **论文摘要 / 中文**:`；摘要不能作为“一句话总结”的子内容。英文复制原始 abstract，不改写，中文只做忠实翻译
3. **术语标注**: 正文中清楚标注关键技术术语；不要创建额外的派生概念笔记
4. **公式格式**: 只保留关键公式，每个公式包含 "含义" + "符号说明" 小节；不要输出 `HTML 公式索引` 或 HTML 自动抽取的零散数学片段列表
5. **关键图固定位置**: 如果论文有 intro/teaser/motivation/overview 图，必须放在 `## 一句话总结` 下方；如果论文有 framework/architecture/method overview/pipeline 图，必须放在 `## 方法详解` 下方。两类图仍然要在 `## 关键图表` 里按 Figure 编号完整出现
6. **图片格式**: `### Figure X: 英文标题 / 中文标题` + 在线URL + `**说明**:`
7. **批判性思考**: 优点、局限性、潜在改进方向、可复现性评估 checklist
8. **关联笔记分类**: 分为 "基于"、"对比"、"方法相关"、"硬件/数据相关"
9. **速查卡片**: ASCII 框格式的快速参考

## 处理规则

1. **图片优先在线链接**：先检查 arXiv HTML 版本 (arxiv.org/html/xxx)，有则用在线图片 URL

## 自动分类与 Zotero 同步（重要）

**不要依赖关键词匹配！** 你需要真正理解论文后自主判断分类。

### 分类判断原则
1. 理解论文的**核心贡献**是什么
2. 问自己：如果我要找这篇论文，我会去哪个分类找？
3. 按**主要贡献**分类，而不是使用的技术
   - 例：用 Diffusion 做机器人控制 → VLA，不是 Diffusion Model
   - 例：用 3DGS 做 SLAM → SLAM，不是 3DGS

### 分类操作
使用 zotero_helper.py 脚本：
- collections: 列出所有分类
- find-collection "名称": 查找分类ID
- move <item_id> <collection_id>: 移动论文

### 何时必须移动
- 当前在 "2025"、"杂项"、"feifeili" 等临时分类 → 必须移动
- 分类与论文内容明显不符 → 移动

## 保存位置

根据你对论文的理解，保存到对应的 Obsidian 目录：
- 基本结构：{notes_root}/对应分类路径/
- 不确定时：{notes_root}/_inbox/

请直接开始处理，不需要确认。提取关键公式、所有图片和表格。"""

    try:
        cmd = [
            _CODEX_BIN,
            'exec',
            '--full-auto',
            '--skip-git-repo-check',
            '-C',
            _CODEX_WORKDIR,
        ]
        if _CODEX_MODEL:
            cmd.extend(['--model', _CODEX_MODEL])
        if _CODEX_EXTRA_ARGS:
            cmd.extend(shlex.split(_CODEX_EXTRA_ARGS))
        cmd.append(prompt)

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=900  # 15分钟超时（因为要提取图片）
        )

        output = result.stdout + result.stderr

        limit_type = detect_limit_error(output)
        if limit_type == 'RATE_LIMIT':
            return False, 'RATE_LIMIT'
        if limit_type == 'QUOTA_LIMIT':
            return False, f'QUOTA_LIMIT|{output[:200]}'

        if result.returncode == 0:
            return True, ''
        else:
            return False, output[:500]

    except subprocess.TimeoutExpired:
        return False, 'TIMEOUT'
    except Exception as e:
        return False, str(e)


def process_collection(collection_name: str, resume: bool = True):
    """处理整个分类的论文"""
    logger.info(f"=== 开始处理分类: {collection_name} ===")

    db_path = copy_zotero_db()

    collection_id, collection_path = get_collection_id_and_path(db_path, collection_name)
    if not collection_id:
        logger.error(f"找不到分类: {collection_name}")
        return

    logger.info(f"分类路径: {collection_path} (ID: {collection_id})")

    papers = get_papers_in_collection(db_path, collection_id)
    logger.info(f"分类下共有 {len(papers)} 篇论文")

    progress = load_progress() if resume else {'completed': [], 'failed': [], 'current': None, 'started_at': None}
    if not progress['started_at']:
        progress['started_at'] = datetime.now().isoformat()

    # 获取已有笔记
    existing_notes = get_existing_notes()
    logger.info(f"Obsidian 中已有 {len(existing_notes)} 篇笔记")

    # 过滤待处理论文
    pending = []
    skipped_existing = 0
    for paper in papers:
        item_id = paper['item_id']
        title = paper['title']

        if item_id in progress['completed']:
            continue

        # 检查是否已有笔记
        if title_matches_note(title, existing_notes):
            logger.info(f"跳过 (已有笔记): {title[:50]}")
            skipped_existing += 1
            progress['completed'].append(item_id)  # 标记为已完成
            continue

        pdf_path = get_pdf_path(db_path, item_id)
        paper_source = {'title': title}

        if pdf_path and os.path.exists(pdf_path):
            paper_source['pdf_path'] = pdf_path
        else:
            # 尝试获取在线来源
            online_source = get_paper_online_source(db_path, item_id)
            if online_source:
                paper_source.update(online_source)
                logger.info(f"无本地 PDF，使用在线来源: {list(online_source.keys())}")
            else:
                logger.warning(f"跳过 (无PDF且无在线来源): {title[:50]}")
                continue

        pending.append({**paper, 'source': paper_source})

    if skipped_existing > 0:
        logger.info(f"跳过已有笔记: {skipped_existing} 篇")
        save_progress(progress)

    logger.info(f"待处理: {len(pending)} 篇")

    wait_time = INITIAL_WAIT

    for i, paper in enumerate(pending):
        item_id = paper['item_id']
        title = paper['title']
        paper_source = paper['source']

        source_type = "PDF" if paper_source.get('pdf_path') else "在线"
        logger.info(f"\n[{i+1}/{len(pending)}] 处理 ({source_type}): {title[:60]}...")
        progress['current'] = {'item_id': item_id, 'title': title}
        save_progress(progress)

        success, error = call_codex(paper_source, collection_path, item_id)

        if success:
            logger.info(f"✓ 完成: {title[:50]}")
            progress['completed'].append(item_id)
            progress['current'] = None
            save_progress(progress)
            wait_time = INITIAL_WAIT

            if i < len(pending) - 1:
                time.sleep(BETWEEN_PAPERS_WAIT)

        elif error == 'RATE_LIMIT':
            logger.warning(f"⏳ Rate limit, 等待 {wait_time} 秒...")
            time.sleep(wait_time)
            wait_time = min(wait_time * WAIT_MULTIPLIER, MAX_WAIT)
            pending.insert(i + 1, paper)  # 重新加入队列

        elif error.startswith('QUOTA_LIMIT'):
            reset_wait = parse_reset_wait_seconds(error)
            if reset_wait:
                logger.warning(f"⏳ 用量上限，等待到重置（约 {reset_wait // 60} 分钟）...")
                time.sleep(reset_wait)
            else:
                wait_for_quota_reset()
            pending.insert(i + 1, paper)  # 重新加入队列

        elif error == 'TIMEOUT':
            logger.error(f"✗ 超时: {title[:50]}")
            progress['failed'].append({'item_id': item_id, 'title': title, 'error': 'TIMEOUT'})
            save_progress(progress)

        else:
            logger.error(f"✗ 失败: {title[:50]} - {error[:100]}")
            progress['failed'].append({'item_id': item_id, 'title': title, 'error': error[:200]})
            save_progress(progress)

    progress['current'] = None
    progress['finished_at'] = datetime.now().isoformat()
    save_progress(progress)

    logger.info("\n=== 处理完成 ===")
    logger.info(f"成功: {len(progress['completed'])} 篇")
    logger.info(f"失败: {len(progress['failed'])} 篇")


def show_status():
    """显示当前进度"""
    progress = load_progress()
    print("\n=== Paper Daemon 状态 ===")
    print(f"开始时间: {progress.get('started_at', 'N/A')}")
    print(f"完成时间: {progress.get('finished_at', '进行中...')}")
    print(f"已完成: {len(progress.get('completed', []))} 篇")
    print(f"失败: {len(progress.get('failed', []))} 篇")

    current = progress.get('current')
    if current:
        print(f"当前处理: {current.get('title', 'N/A')[:60]}")

    if progress.get('failed'):
        print("\n失败的论文:")
        for item in progress['failed'][:5]:
            print(f"  - {item['title'][:50]}: {item['error'][:50]}")


def main():
    parser = argparse.ArgumentParser(description='Paper Reading Daemon')
    parser.add_argument('--collection', '-c', type=str, help='Zotero 分类名称')
    parser.add_argument('--status', '-s', action='store_true', help='显示当前状态')
    parser.add_argument('--no-resume', action='store_true', help='不恢复之前的进度')
    parser.add_argument('--list', '-l', action='store_true', help='列出所有 Zotero 分类')

    args = parser.parse_args()

    if args.status:
        show_status()
        return

    if args.list:
        db_path = copy_zotero_db()
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT c.collectionName, COUNT(ci.itemID) as count
            FROM collections c
            LEFT JOIN collectionItems ci ON c.collectionID = ci.collectionID
            GROUP BY c.collectionID
            HAVING count > 0
            ORDER BY c.collectionName
        """)
        print("\n=== Zotero 分类 ===")
        for name, count in cursor.fetchall():
            print(f"  {name}: {count} 篇")
        conn.close()
        return

    if not args.collection:
        parser.print_help()
        return

    # 检查是否已有进程在运行
    if not acquire_lock():
        logger.error("另一个 paper_daemon 进程正在运行！请先停止它或删除 ~/.codex/paper_daemon.pid")
        return

    try:
        process_collection(args.collection, resume=not args.no_resume)
    finally:
        release_lock()


if __name__ == '__main__':
    main()
