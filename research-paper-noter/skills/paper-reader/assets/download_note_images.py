#!/usr/bin/env python3
"""Selectively download unreachable images in Obsidian markdown notes.

Usage:
    python3 download_note_images.py <note.md>

For each external image link ![...](https://...):
  - Reachable (HTTP 200 within 10s) → keep as-is
  - Unreachable → download to assets/ and replace with Obsidian wikilink
"""

import asyncio
import json
import os
import re
import subprocess
import sys
from pathlib import Path

CURL_TIMEOUT = 10
CONCURRENCY = 5


def parse_note(text: str) -> list[dict]:
    """Extract all external image references with their positions.

    Returns list of dicts: {full_match, alt, url, start, end}
    """
    pattern = re.compile(r"!\[([^\]]*)\]\((https?://[^)\s]+)\)")
    images = []
    for m in pattern.finditer(text):
        images.append({
            "full_match": m.group(0),
            "alt": m.group(1),
            "url": m.group(2),
            "start": m.start(),
            "end": m.end(),
        })
    return images


def get_method_name(note_path: Path) -> str:
    """Extract method name from note filename (stem)."""
    return note_path.stem


def extract_arxiv_id(url: str) -> str:
    """Try to extract arxiv_id from a URL."""
    m = re.search(r"(\d{4}\.\d{4,5})", url)
    return m.group(1) if m else ""


async def check_url(url: str, sem: asyncio.Semaphore) -> bool:
    """Check if a URL is reachable (HTTP 200) using curl."""
    async with sem:
        try:
            proc = await asyncio.create_subprocess_exec(
                "curl", "-sL", "-o", "/dev/null", "-w", "%{http_code}",
                "--max-time", str(CURL_TIMEOUT), url,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=CURL_TIMEOUT + 5)
            code = stdout.decode().strip() if stdout else ""
            return code == "200"
        except (asyncio.TimeoutError, Exception):
            return False


async def download_image(url: str, dest: Path, sem: asyncio.Semaphore) -> bool:
    """Download an image from URL to dest path. Returns True on success."""
    async with sem:
        try:
            proc = await asyncio.create_subprocess_exec(
                "curl", "-sL", "--max-time", str(CURL_TIMEOUT + 10),
                "-o", str(dest), url,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.communicate(), timeout=CURL_TIMEOUT + 15)
            # Verify file exists and is non-trivial
            return dest.exists() and dest.stat().st_size > 1024
        except (asyncio.TimeoutError, Exception):
            return False


async def try_pdf_extract(arxiv_id: str, assets_dir: Path, method_name: str,
                          fig_num: int, sem: asyncio.Semaphore) -> Path | None:
    """Try to extract a figure from the arXiv PDF as fallback."""
    if not arxiv_id:
        return None
    async with sem:
        try:
            pdf_path = f"/tmp/arxiv_{arxiv_id}.pdf"
            prefix = str(assets_dir / f"{method_name}_pdf_fig")
            # Download PDF if not cached
            if not Path(pdf_path).exists():
                proc = await asyncio.create_subprocess_exec(
                    "curl", "-sL", "--max-time", "30",
                    "-o", pdf_path, f"https://arxiv.org/pdf/{arxiv_id}.pdf",
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                await asyncio.wait_for(proc.communicate(), timeout=35)
            # Extract images with pdfimages
            if Path(pdf_path).exists():
                proc = await asyncio.create_subprocess_exec(
                    "pdfimages", "-png", pdf_path, prefix,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                await asyncio.wait_for(proc.communicate(), timeout=30)
                # Find extracted images > 10KB
                extracted = sorted(assets_dir.glob(f"{method_name}_pdf_fig-*.png"))
                large = [f for f in extracted if f.stat().st_size > 10240]
                if fig_num - 1 < len(large):
                    return large[fig_num - 1]
        except (asyncio.TimeoutError, Exception):
            pass
    return None


def update_frontmatter(text: str) -> str:
    """Update image_source from 'online' to 'mixed' in frontmatter."""
    return re.sub(
        r"^(image_source:\s*)online\s*$",
        r"\1mixed",
        text,
        count=1,
        flags=re.MULTILINE,
    )


async def process_note(note_path: Path) -> dict:
    """Main processing logic. Returns summary dict."""
    text = note_path.read_text(encoding="utf-8")
    images = parse_note(text)

    if not images:
        print(f"No external images found in {note_path.name}")
        return {"total": 0, "reachable": 0, "localized": 0, "failed": 0}

    method_name = get_method_name(note_path)
    assets_dir = note_path.parent / "assets"
    sem = asyncio.Semaphore(CONCURRENCY)

    print(f"Found {len(images)} external image(s) in {note_path.name}")

    # Step 1: Check reachability concurrently
    check_tasks = [check_url(img["url"], sem) for img in images]
    reachable = await asyncio.gather(*check_tasks)

    # Step 2: Process unreachable images
    replacements = {}  # full_match -> new_reference
    localized = 0
    failed = 0

    for i, (img, is_ok) in enumerate(zip(images, reachable)):
        if is_ok:
            print(f"  [OK] {img['url'][:80]}")
            continue

        fig_num = i + 1
        ext = Path(img["url"]).suffix or ".png"
        if ext not in (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"):
            ext = ".png"
        local_name = f"{method_name}_fig{fig_num}{ext}"
        local_path = assets_dir / local_name

        # Ensure assets dir exists
        assets_dir.mkdir(parents=True, exist_ok=True)

        # Try direct download first
        print(f"  [DL] {img['url'][:80]}")
        ok = await download_image(img["url"], local_path, sem)

        # Fallback: try PDF extraction
        if not ok:
            arxiv_id = extract_arxiv_id(img["url"])
            if arxiv_id:
                print(f"  [PDF fallback] arxiv:{arxiv_id} fig{fig_num}")
                pdf_path = await try_pdf_extract(arxiv_id, assets_dir, method_name, fig_num, sem)
                if pdf_path:
                    # Rename to our convention
                    pdf_path.rename(local_path)
                    ok = True

        if ok and local_path.exists() and local_path.stat().st_size > 1024:
            new_ref = f"![[{local_name}|600]]"
            replacements[img["full_match"]] = new_ref
            localized += 1
            print(f"  [OK] Localized → {local_name}")
        else:
            failed += 1
            # Clean up partial download
            if local_path.exists():
                local_path.unlink()
            print(f"  [FAIL] Could not download {img['url'][:80]}")

    # Step 3: Apply replacements to text
    if replacements:
        new_text = text
        for old, new in replacements.items():
            new_text = new_text.replace(old, new)
        new_text = update_frontmatter(new_text)
        note_path.write_text(new_text, encoding="utf-8")
        print(f"Updated {note_path.name}: {localized} image(s) localized")

    total = len(images)
    reachable_count = sum(1 for r in reachable if r)
    return {
        "total": total,
        "reachable": reachable_count,
        "localized": localized,
        "failed": failed,
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 download_note_images.py <note.md>", file=sys.stderr)
        sys.exit(1)

    note_path = Path(sys.argv[1]).expanduser().resolve()
    if not note_path.exists():
        print(f"File not found: {note_path}", file=sys.stderr)
        sys.exit(1)

    result = asyncio.run(process_note(note_path))

    print(f"\nSummary: {result['total']} images — "
          f"{result['reachable']} reachable, "
          f"{result['localized']} localized, "
          f"{result['failed']} failed")

    # Output JSON for programmatic use
    print(json.dumps(result), file=sys.stderr)


if __name__ == "__main__":
    main()
