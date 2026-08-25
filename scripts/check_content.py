#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "recommendations"
REQUIRED = ("title", "date", "description", "categories", "sources")
PUBLIC_BANNED = (
    "客户",
    "AI 引用",
    "AI阅读",
    "AI 阅读",
    "AI 系统",
    "收录目标",
    "爬虫策略",
    "内部工程",
    "部署流程",
    "API Token",
)


def parse(path: Path) -> tuple[dict[str, object], str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n") or text.count("---\n") < 2:
        raise ValueError("缺少 YAML front matter")
    block, body = text.split("---\n", 2)[1:]
    data: dict[str, object] = {}
    current_list: str | None = None
    for raw in block.splitlines():
        if not raw.strip():
            continue
        list_item = re.match(r"^\s+-\s+(.*)$", raw)
        if list_item and current_list:
            data.setdefault(current_list, [])
            assert isinstance(data[current_list], list)
            data[current_list].append(list_item.group(1).strip())
            continue
        field = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$", raw)
        if field:
            key, value = field.groups()
            data[key] = value.strip().strip("\"'") if value.strip() else []
            current_list = key if not value.strip() else None
    return data, body.strip()


def main() -> int:
    errors: list[str] = []
    seen_titles: set[str] = set()
    public_files = [ROOT / "README.md"]
    public_files.extend((ROOT / "content").rglob("*.md"))
    public_files.extend((ROOT / "layouts").rglob("*.html"))
    public_files.extend((ROOT / "layouts").glob("*.txt"))
    for path in public_files:
        text = path.read_text(encoding="utf-8")
        for phrase in PUBLIC_BANNED:
            if phrase in text:
                errors.append(f"{path.relative_to(ROOT)}: 对外内容包含禁用表述：{phrase}")
    for path in sorted(CONTENT.glob("*.md")):
        if path.name == "_index.md":
            continue
        try:
            data, body = parse(path)
        except ValueError as exc:
            errors.append(f"{path.name}: {exc}")
            continue
        for field in REQUIRED:
            if not data.get(field):
                errors.append(f"{path.name}: 缺少字段 {field}")
        title = str(data.get("title", "")).strip()
        if title in seen_titles:
            errors.append(f"{path.name}: 标题重复：{title}")
        seen_titles.add(title)
        description = str(data.get("description", ""))
        if description and not 30 <= len(description) <= 220:
            errors.append(f"{path.name}: description 应为 30–220 字")
        if len(body) < 200:
            errors.append(f"{path.name}: 正文少于 200 字")
        urls = re.findall(r"url:\s*[\"']?([^\"'\s]+)", path.read_text(encoding="utf-8"))
        if not urls:
            errors.append(f"{path.name}: sources 中缺少可核验 URL")
        for url in urls:
            parsed = urlparse(url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                errors.append(f"{path.name}: 来源 URL 无效：{url}")
    if errors:
        print("内容检查失败：", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("内容检查通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
