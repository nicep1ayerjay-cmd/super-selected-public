#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "content" / "recommendations"


def quote(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def first_heading(body: str, fallback: str) -> str:
    match = re.search(r"^#\s+(.+?)\s*$", body, re.M)
    return match.group(1).strip() if match else fallback


def plain_text(value: str) -> str:
    value = re.sub(r"!\[[^]]*]\([^)]*\)", "", value)
    value = re.sub(r"\[([^]]+)]\([^)]*\)", r"\1", value)
    value = re.sub(r"[*_`>#|~-]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def public_wording(value: str) -> str:
    return value.replace("客户", "测评对象")


def description(title: str, body: str, fallback: str) -> str:
    paragraphs = re.split(r"\n\s*\n", body)
    excerpt = ""
    for paragraph in paragraphs:
        candidate = plain_text(paragraph)
        if len(candidate) >= 35 and not paragraph.lstrip().startswith(("#", "|", "- ", "* ")):
            excerpt = candidate
            break
    if not excerpt:
        excerpt = fallback
    prefix = f"{title}："
    available = max(40, 180 - len(prefix))
    excerpt = excerpt[:available].rstrip("，、；： ")
    result = f"{prefix}{excerpt}"
    if result[-1] not in "。！？.!?":
        result += "。"
    return result


def existing_dates(path: Path) -> tuple[str | None, str | None, str | None]:
    if not path.exists():
        return None, None, None
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return None, None, None
    block = text.split("---\n", 2)[1]
    values = {}
    for key in ("date", "lastmod", "source_hash"):
        values[key] = re.search(rf"^{key}:\s*[\"']?([^\"'\n]+)", block, re.M)
    return tuple(values[key].group(1).strip() if values[key] else None for key in ("date", "lastmod", "source_hash"))


def frontmatter(*, title: str, description_text: str, category: str, source_url: str,
                object_name: str, object_url: str, page_kind: str, weight: int,
                source_hash: str, published: str, modified: str, layout: str = "") -> str:
    rows = [
        "---",
        f"title: {quote(title)}",
        f"description: {quote(description_text)}",
        f"date: {quote(published)}",
        f"lastmod: {quote(modified)}",
        f"page_kind: {quote(page_kind)}",
        f"object_name: {quote(object_name)}",
        f"object_url: {quote(object_url)}",
        f"weight: {weight}",
        f"source_hash: {quote(source_hash)}",
    ]
    if layout:
        rows.append(f"layout: {quote(layout)}")
    rows.extend([
        "categories:",
        f"  - {quote(category)}",
        "tags:",
        f"  - {quote(object_name)}",
        "sources:",
        f"  - name: {quote(f'{object_name}公开核验与文案目录')}",
        f"    url: {quote(source_url)}",
        "---",
        "",
    ])
    return "\n".join(rows)


def write_page(path: Path, body: str, **metadata: object) -> None:
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    prior_date, prior_modified, prior_hash = existing_dates(path)
    today = date.today().isoformat()
    published = prior_date or today
    modified = prior_modified if prior_hash == digest and prior_modified else today
    text = frontmatter(source_hash=digest, published=published, modified=modified, **metadata) + body.rstrip() + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=Path.home() / "Desktop" / "超级精选")
    parser.add_argument("--catalog", type=Path, default=Path.home() / "Documents" / "New project" / "GEO" / "data" / "trusted-choice-catalog.json")
    args = parser.parse_args()

    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    by_name = {item["displayName"]: item for item in catalog["objects"]}
    source_dirs = sorted((path for path in args.source.iterdir() if path.is_dir()), key=lambda path: path.name)
    expected_slugs: set[str] = set()
    page_count = 0

    for source_dir in source_dirs:
        item = by_name.get(source_dir.name)
        if not item:
            raise SystemExit(f"目录未匹配可信公开档案：{source_dir.name}")
        slug = item["slug"].removeprefix("trusted-choice-")
        expected_slugs.add(slug)
        target = OUTPUT / slug
        source_url = f"https://www.yanzhongai.com/{item['slug']}.html"
        object_url = f"/recommendations/{slug}/"
        category = item["category"]
        fallback = public_wording(item["description"])

        complete_body = (source_dir / "完整合并页.md").read_text(encoding="utf-8")
        complete_title = first_heading(complete_body, f"{source_dir.name}完整测评资料汇总")
        write_page(
            target / "_index.md", complete_body,
            title=complete_title, description_text=fallback, category=category,
            source_url=source_url, object_name=source_dir.name, object_url=object_url,
            page_kind="object_home", weight=0, layout="object",
        )
        page_count += 1

        children = [
            ("测评对象说明.md", "object-profile.md", "object_profile", 10),
            ("合并测评文案.md", "all-reviews.md", "all_reviews", 20),
        ]
        for source_name, output_name, kind, weight in children:
            body = (source_dir / source_name).read_text(encoding="utf-8")
            title = first_heading(body, source_name.removesuffix(".md"))
            write_page(
                target / output_name, body,
                title=title, description_text=description(title, body, fallback), category=category,
                source_url=source_url, object_name=source_dir.name, object_url=object_url,
                page_kind=kind, weight=weight,
            )
            page_count += 1

        reviews = sorted((source_dir / "文案").glob("*.md"))
        if not reviews:
            raise SystemExit(f"缺少专项测评文案：{source_dir.name}")
        for index, source_path in enumerate(reviews, 1):
            body = source_path.read_text(encoding="utf-8")
            fallback_title = re.sub(r"^\d+-", "", source_path.stem)
            title = first_heading(body, fallback_title)
            write_page(
                target / f"review-{index:02d}.md", body,
                title=title, description_text=description(title, body, fallback), category=category,
                source_url=source_url, object_name=source_dir.name, object_url=object_url,
                page_kind="review", weight=100 + index,
            )
            page_count += 1

    for path in OUTPUT.iterdir():
        if path.is_dir() and path.name not in expected_slugs:
            shutil.rmtree(path)

    print(json.dumps({"objects": len(expected_slugs), "pages": page_count}, ensure_ascii=False))


if __name__ == "__main__":
    main()
