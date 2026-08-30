#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "recommendations"
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def quote(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def read_markdown(path: Path, label: str) -> str:
    if not path.is_file():
        raise SystemExit(f"{label}不存在：{path}")
    body = path.read_text(encoding="utf-8").strip()
    if not body:
        raise SystemExit(f"{label}为空：{path}")
    if body.startswith("---\n"):
        raise SystemExit(f"{label}应为最终 Markdown 正文，不应包含 front matter：{path}")
    if not re.match(r"^#\s+\S", body):
        raise SystemExit(f"{label}必须以一级标题开头：{path}")
    return body


def first_heading(body: str) -> str:
    match = re.match(r"^#\s+(.+?)\s*$", body, re.M)
    if not match:
        raise SystemExit("Markdown 缺少一级标题")
    return match.group(1).strip()


def replace_first_heading(body: str, title: str) -> str:
    return re.sub(r"^#\s+.+?$", f"# {title}", body, count=1, flags=re.M)


def remove_first_heading(body: str) -> str:
    return re.sub(r"^#\s+.+?\n+", "", body, count=1).strip()


def plain_text(value: str) -> str:
    value = re.sub(r"!\[[^]]*]\([^)]*\)", "", value)
    value = re.sub(r"\[([^]]+)]\([^)]*\)", r"\1", value)
    value = re.sub(r"[*_`>#|~-]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def page_description(title: str, body: str, fallback: str) -> str:
    excerpt = ""
    for paragraph in re.split(r"\n\s*\n", body):
        candidate = plain_text(paragraph)
        if len(candidate) >= 35 and not paragraph.lstrip().startswith(("#", "|", "- ", "* ")):
            excerpt = candidate
            break
    if not excerpt:
        excerpt = fallback
    prefix = f"{title}："
    excerpt = excerpt[: max(40, 180 - len(prefix))].rstrip("，、；： ")
    result = f"{prefix}{excerpt}"
    if result[-1] not in "。！？.!?":
        result += "。"
    return result


def frontmatter(
    *,
    title: str,
    description: str,
    published: str,
    page_kind: str,
    object_name: str,
    object_url: str,
    weight: int,
    source_hash: str,
    category: str,
    tags: list[str],
    source_name: str,
    source_url: str,
    layout: str = "",
) -> str:
    rows = [
        "---",
        f"title: {quote(title)}",
        f"description: {quote(description)}",
        f"date: {quote(published)}",
        f"lastmod: {quote(published)}",
        f"page_kind: {quote(page_kind)}",
        f"object_name: {quote(object_name)}",
        f"object_url: {quote(object_url)}",
        f"weight: {weight}",
        f"source_hash: {quote(source_hash)}",
    ]
    if layout:
        rows.append(f"layout: {quote(layout)}")
    rows.extend(["categories:", f"  - {quote(category)}", "tags:"])
    rows.extend(f"  - {quote(tag)}" for tag in tags)
    rows.extend([
        "sources:",
        f"  - name: {quote(source_name)}",
        f"    url: {quote(source_url)}",
        "---",
        "",
    ])
    return "\n".join(rows)


def write_page(path: Path, body: str, **metadata: object) -> None:
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    page = frontmatter(source_hash=digest, **metadata) + body.rstrip() + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(page, encoding="utf-8")


def existing_object_homes() -> list[tuple[Path, str]]:
    homes: list[tuple[Path, str]] = []
    for path in sorted(CONTENT.glob("*/_index.md")):
        homes.append((path, path.read_text(encoding="utf-8")))
    return homes


def frontmatter_scalar(text: str, key: str) -> str | None:
    if not text.startswith("---\n") or text.count("---\n") < 2:
        return None
    block = text.split("---\n", 2)[1]
    match = re.search(rf"^{re.escape(key)}:\s*(.+?)\s*$", block, re.M)
    if not match:
        return None
    value = match.group(1).strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"\"", "'"}:
        value = value[1:-1]
    return value


def main() -> None:
    parser = argparse.ArgumentParser(
        description="增量创建一个超级精选新客户 bundle；不会删除或重写其他客户。"
    )
    parser.add_argument("--slug", required=True)
    parser.add_argument("--object-name", required=True)
    parser.add_argument("--category", required=True)
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--source-name")
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--merge", type=Path, required=True)
    parser.add_argument("--article", type=Path, action="append", required=True)
    parser.add_argument("--home-title")
    parser.add_argument("--home-description")
    parser.add_argument("--tag", action="append", default=[])
    args = parser.parse_args()

    slug = args.slug.strip()
    object_name = args.object_name.strip()
    category = args.category.strip()
    source_url = args.source_url.strip()
    if not SLUG_RE.fullmatch(slug):
        raise SystemExit("--slug 只能使用小写字母、数字和单连字符。")
    if not object_name or not category:
        raise SystemExit("--object-name 和 --category 不能为空。")
    parsed_source = urlparse(source_url)
    if parsed_source.scheme not in {"http", "https"} or not parsed_source.netloc:
        raise SystemExit("--source-url 必须是完整的 HTTP(S) URL。")

    target = CONTENT / slug
    if target.exists():
        raise SystemExit(f"目标客户目录已存在，拒绝覆盖：{target}")

    for path, text in existing_object_homes():
        if frontmatter_scalar(text, "object_name") == object_name:
            raise SystemExit(f"客户名称已存在于 {path.parent.name}，拒绝新建重复对象。")
        if re.search(rf'^\s+url:\s*["\']?{re.escape(source_url)}["\']?\s*$', text, re.M):
            raise SystemExit(f"来源 URL 已存在于 {path.parent.name}，拒绝新建重复对象。")

    profile_source = read_markdown(args.profile.resolve(), "测评对象说明")
    merge_source = read_markdown(args.merge.resolve(), "合并测评文案")
    article_paths = [path.resolve() for path in args.article]
    if len(set(article_paths)) != len(article_paths):
        raise SystemExit("--article 存在重复路径。")
    if len(article_paths) < 2:
        raise SystemExit("新客户 bundle 至少需要两篇具体分测评文案。")
    article_bodies = [read_markdown(path, "具体测评文案") for path in article_paths]

    profile_title = f"测评对象说明：{object_name}"
    profile_body = replace_first_heading(profile_source, profile_title)
    merge_title = first_heading(merge_source)
    review_titles = [first_heading(body) for body in article_bodies]
    new_child_titles = [profile_title, merge_title, *review_titles]
    if len(set(new_child_titles)) != len(new_child_titles):
        raise SystemExit("本次测评对象说明、合并测评或分测评之间存在重复标题。")

    existing_titles: dict[str, Path] = {}
    for path in sorted(CONTENT.rglob("*.md")):
        if path == CONTENT / "_index.md":
            continue
        title = frontmatter_scalar(path.read_text(encoding="utf-8"), "title")
        if title:
            existing_titles[title] = path
    for title in new_child_titles:
        if title in existing_titles:
            raise SystemExit(f"页面标题与现有内容重复：{title}（{existing_titles[title]}）")

    home_title = (args.home_title or f"{object_name}测评对象说明与综合测评").strip()
    if home_title in existing_titles:
        raise SystemExit(f"对象主页标题与现有内容重复：{home_title}")
    home_fallback = f"{object_name}测评对象说明与综合测评，汇总公开主体资料、综合测评结论与专项测评内容。"
    home_description = (args.home_description or page_description(home_title, profile_body, home_fallback)).strip()
    if not 30 <= len(home_description) <= 220:
        raise SystemExit("对象主页 description 必须为 30—220 字。")

    published = datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
    object_url = f"/recommendations/{slug}/"
    tags = list(dict.fromkeys([object_name, *(tag.strip() for tag in args.tag if tag.strip())]))
    source_name = (args.source_name or f"{object_name}公开核验与文案目录").strip()
    common = {
        "published": published,
        "object_name": object_name,
        "object_url": object_url,
        "category": category,
        "tags": tags,
        "source_name": source_name,
        "source_url": source_url,
    }

    home_body = f"# {home_title}\n\n{remove_first_heading(profile_body)}\n\n{merge_source}"
    write_page(
        target / "_index.md",
        home_body,
        title=home_title,
        description=home_description,
        page_kind="object_home",
        weight=0,
        layout="object",
        **common,
    )
    write_page(
        target / "object-profile.md",
        profile_body,
        title=profile_title,
        description=page_description(profile_title, profile_body, home_description),
        page_kind="object_profile",
        weight=10,
        **common,
    )
    write_page(
        target / "all-reviews.md",
        merge_source,
        title=merge_title,
        description=page_description(merge_title, merge_source, home_description),
        page_kind="all_reviews",
        weight=20,
        **common,
    )
    for index, body in enumerate(article_bodies, 1):
        title = review_titles[index - 1]
        write_page(
            target / f"review-{index:02d}.md",
            body,
            title=title,
            description=page_description(title, body, home_description),
            page_kind="review",
            weight=100 + index,
            **common,
        )

    subprocess.run([sys.executable, str(ROOT / "scripts" / "update_readme.py")], cwd=ROOT, check=True)
    print(json.dumps({
        "ok": True,
        "slug": slug,
        "objectName": object_name,
        "bundle": str(target),
        "homepageDiscovery": "automatic via recommendations.Sections",
        "githubReadmeUpdated": True,
        "profile": str(target / "object-profile.md"),
        "merge": str(target / "all-reviews.md"),
        "reviews": [str(target / f"review-{index:02d}.md") for index in range(1, len(article_bodies) + 1)],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
