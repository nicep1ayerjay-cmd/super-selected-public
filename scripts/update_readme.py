#!/usr/bin/env python3
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "recommendations"
README = ROOT / "README.md"
START = "<!-- SUPER_SELECTED:START -->"
END = "<!-- SUPER_SELECTED:END -->"


def frontmatter(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError(f"缺少 YAML front matter: {path}")
    block = text.split("---\n", 2)[1]
    data: dict[str, object] = {}
    current_list: str | None = None
    for raw in block.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        item = re.match(r"^\s+-\s+[\"']?(.*?)[\"']?\s*$", raw)
        if item and current_list:
            data.setdefault(current_list, [])
            assert isinstance(data[current_list], list)
            data[current_list].append(item.group(1))
            continue
        field = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$", raw)
        if not field:
            continue
        key, value = field.groups()
        value = value.strip().strip("\"'")
        if value:
            data[key] = value
            current_list = None
        else:
            data[key] = []
            current_list = key
    return data


def main() -> None:
    entries: list[tuple[datetime, Path, dict[str, object]]] = []
    for path in CONTENT.glob("*.md"):
        if path.name == "_index.md":
            continue
        data = frontmatter(path)
        if str(data.get("draft", "false")).lower() == "true":
            continue
        date = datetime.fromisoformat(str(data["date"]).replace("Z", "+00:00"))
        entries.append((date, path, data))
    entries.sort(key=lambda item: item[0], reverse=True)

    lines: list[str] = []
    if not entries:
        lines.append("暂无已发布推荐。")
    else:
        lines.append(f"当前共发布 **{len(entries)}** 篇，以下显示最新 20 篇。")
        lines.append("")
        for date, path, data in entries[:20]:
            title = str(data["title"])
            categories = data.get("categories", [])
            category = categories[0] if isinstance(categories, list) and categories else "综合"
            slug = path.stem
            site_url = f"https://super-selected-daily.pages.dev/recommendations/{slug}/"
            repo_path = f"content/recommendations/{path.name}"
            lines.append(
                f"- {date:%Y-%m-%d} · {category} · [{title}]({site_url}) "
                f"([Markdown]({repo_path}))"
            )

    readme = README.read_text(encoding="utf-8")
    replacement = f"{START}\n\n" + "\n".join(lines) + f"\n\n{END}"
    updated, count = re.subn(
        re.escape(START) + r".*?" + re.escape(END),
        replacement,
        readme,
        flags=re.S,
    )
    if count != 1:
        raise SystemExit("README 自动区块标记缺失或重复")
    README.write_text(updated, encoding="utf-8")


if __name__ == "__main__":
    main()
