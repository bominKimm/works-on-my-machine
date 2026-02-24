"""
Knowledge Base 더미 데이터 생성: 메타데이터 + 문서 본문 + manifest.

- 카테고리별로 LLM을 호출해 가상 문서 섹션을 많이 생성.
- .env의 OPENAI_API_KEY를 사용 (로드 후 API 호출).

실행: 프로젝트 루트(agenthon)에서 `python -m data.generate_dummy_data`
"""

import json
import random
import sys
from pathlib import Path

# 직접 실행 시 프로젝트 루트를 path에 추가
if __name__ == "__main__" and __file__:
    _root = Path(__file__).resolve().parent.parent
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))

# .env 로드 (OPENAI_API_KEY 등) — 반드시 다른 data import보다 먼저
import data.env  # noqa: F401, E402

from data.kb import save_manifest
from data.schema import CATEGORIES, POST_TEMPLATES, AUTHOR_NAMES, DOCUMENT_THEMES_BY_CATEGORY
from data.llm_content import generate_sections_for_category

DATA_DIR = Path(__file__).resolve().parent
RANDOM_SEED = 42

# 카테고리당 생성할 게시글 수 (여기서 조절). 총 게시글 = 5 × POSTS_PER_CATEGORY
POSTS_PER_CATEGORY = 3


def generate_categories() -> list[dict]:
    return list(CATEGORIES)


def generate_posts(categories: list[dict]) -> list[dict]:
    posts = []
    post_seq = 1
    base_ts = "2025-05-12T09:00:00Z"
    for cat in categories:
        cid = cat["category_id"]
        templates = POST_TEMPLATES.get(cid, [])
        if not templates:
            continue
        for i in range(POSTS_PER_CATEGORY):
            t = templates[i % len(templates)]
            post_id = f"POST-SEC-2025-{post_seq:03d}"
            posts.append({
                "post_id": post_id,
                "category_id": cid,
                "doc_type": t["doc_type"],
                "title": f"{t['title_prefix']}/개정/(2025.05.{10 + post_seq % 20:02d})공지",
                "author_name": random.choice(AUTHOR_NAMES),
                "view_count": random.randint(100, 1500),
                "created_at": base_ts,
                "updated_at": base_ts,
                "file_prefix": t["file_prefix"],
            })
            post_seq += 1
    return posts


def generate_files(posts: list[dict]) -> list[dict]:
    """게시글당 파일 1개 또는 필요 시 v1+v2 생성. 유동적으로 적용."""
    files = []
    file_seq = 1
    base_ts = "2025-05-12T09:00:00Z"
    for p in posts:
        pid = p["post_id"]
        prefix = p.get("file_prefix", "doc")
        has_v2 = file_seq % 3 == 0  # 일부만 v2 있음 (필요 시 비율 조정)
        if has_v2:
            files.append({"file_id": f"FILE-SEC-2025-{file_seq:03d}-V1", "post_id": pid, "file_name": f"{prefix}_v1.0.pdf", "version_tag": "v1.0", "status": "deprecated", "uploaded_at": base_ts})
            file_seq += 1
            files.append({"file_id": f"FILE-SEC-2025-{file_seq:03d}-V2", "post_id": pid, "file_name": f"{prefix}_v2.0.pdf", "version_tag": "v2.0", "status": "active", "uploaded_at": base_ts})
        else:
            files.append({"file_id": f"FILE-SEC-2025-{file_seq:03d}-V1", "post_id": pid, "file_name": f"{prefix}_v1.0.pdf", "version_tag": "v1.0", "status": "active", "uploaded_at": base_ts})
        file_seq += 1
    return files


def build_document_content(
    file_meta: dict,
    category: dict,
    sections: list[dict],
) -> str:
    """공지/정보글처럼: 문서 제목 한 번, 각 절은 소제목만(반복 없음)."""
    lines = [
        f"# {category.get('category_name', '')}\n",
        f"문서: {file_meta.get('file_name', file_meta['file_id'])}",
        f"버전: {file_meta.get('version_tag', '')}",
        f"상태: {file_meta.get('status', '')}\n",
    ]
    if sections:
        doc_title = sections[0].get("chapter_level_1", "").strip()
        if doc_title:
            lines.append(f"## {doc_title}\n")
    for s in sections:
        lines.append(f"### {s['chapter_level_2']}\n\n{s['content']}\n")
    return "\n".join(lines)


def write_documents_and_manifest(
    files: list[dict],
    posts: list[dict],
    categories: list[dict],
    generate_sections_for_file,
) -> tuple[int, int]:
    """
    각 파일마다 generate_sections_for_file(f, post, cat) 로 섹션 생성 후 본문 저장 + manifest 수집.
    문서(파일)별로 다른 본문이 나오도록 파일 단위로 섹션을 만든다.
    """
    post_by_id = {p["post_id"]: p for p in posts}
    cat_by_id = {c["category_id"]: c for c in categories}
    manifest_docs = []
    count = 0
    for idx, f in enumerate(files, 1):
        post = post_by_id.get(f["post_id"])
        if not post:
            continue
        cid = post["category_id"]
        cat = cat_by_id.get(cid, {})
        print(f"  Document {idx}/{len(files)}: {f['file_id']}...")
        sections = generate_sections_for_file(f, post, cat, file_index=idx)
        if not sections:
            continue
        content = build_document_content(f, cat, sections)
        rel_path = f"documents/{cid}/{post['post_id']}/{f['file_id']}.txt"
        out_path = DATA_DIR / rel_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(content, encoding="utf-8")
        count += 1
        # manifest용 metadata: status는 소문자로 (RAG 필터 status=active 와 일치)
        status = (f.get("status") or "active").lower()
        manifest_docs.append({
            "id": f["file_id"],
            "path": rel_path,
            "metadata": {
                "status": status,
                "collection": cid,
                "version": f.get("version_tag", ""),
            },
        })
    # CAT-006 개발 설계 보안성 검토용 정적 문서 추가 (RAG 풍부화)
    design_review_dir = DATA_DIR / "documents" / "CAT-006"
    if design_review_dir.exists():
        for p in sorted(design_review_dir.glob("DESIGN-REVIEW-*.txt")):
            rel_path = str(p.relative_to(DATA_DIR)).replace("\\", "/")
            manifest_docs.append({
                "id": p.stem,
                "path": rel_path,
                "metadata": {"status": "active", "collection": "CAT-006", "version": "1.0"},
            })
    save_manifest(DATA_DIR, manifest_docs)
    return count, len(manifest_docs)


def main() -> None:
    random.seed(RANDOM_SEED)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    categories = generate_categories()
    posts = generate_posts(categories)
    files = generate_files(posts)

    for name, data in [
        ("categories.json", categories),
        ("posts.json", posts),
        ("files.json", files),
    ]:
        path = DATA_DIR / name
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Written: {path} (items: {len(data)})")

    # 문서(파일)마다 LLM 호출 → 문서마다 다른 본문 생성 (문서명·버전·유형·제목을 맥락으로 전달)
    post_by_id = {p["post_id"]: p for p in posts}
    cat_by_id = {c["category_id"]: c for c in categories}

    def generate_sections_for_file(file_meta: dict, post: dict, category: dict, file_index: int = 1) -> list[dict]:
        cid = category["category_id"]
        name = category.get("category_name", cid)
        desc = category.get("description", "")
        themes = DOCUMENT_THEMES_BY_CATEGORY.get(cid, [])
        document_theme = themes[(file_index - 1) % len(themes)] if themes else None
        doc_context = (
            f"게시글 ID: {post.get('post_id')}, 문서 ID: {file_meta.get('file_id')}. "
            f"문서명: {file_meta.get('file_name', file_meta['file_id'])}, 버전: {file_meta.get('version_tag')}, "
            f"유형: {post.get('doc_type')}, 제목: {post.get('title', '')}"
        )
        return generate_sections_for_category(
            cid, name, desc, num_sections=15,
            document_theme=document_theme,
            document_context=doc_context,
        )

    n_docs, n_manifest = write_documents_and_manifest(files, posts, categories, generate_sections_for_file)
    print(f"Written: {DATA_DIR / 'documents'} (documents: {n_docs})")
    print(f"Written: {DATA_DIR / 'manifest.json'} (entries: {n_manifest})")
    print("Done. Next: python -m data.rag index status=active")


if __name__ == "__main__":
    main()
