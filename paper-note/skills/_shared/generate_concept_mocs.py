#!/usr/bin/env python3

import json


def main() -> int:
    summary = {
        "status": "skipped",
        "reason": "concept-mocs-disabled",
        "message": "概念库目录页已废弃，不再生成。",
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
