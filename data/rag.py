"""
범용 RAG: manifest 기반 문서 로드 → 청킹 → 임베딩 → 벡터 스토어 저장/검색.

- 문서 목록은 manifest.json 단일 소스 (id, path, metadata).
- 인제스트 시 metadata_filter로 포함할 문서만 선택 (예: status=active).
- .env 파일에서 OpenAI/Azure 키 로드.
"""

import json
import os
import re
from pathlib import Path

import data.env  # noqa: F401 - load .env before reading os.environ
from data.kb import get_documents, manifest_path, metadata_matches

DATA_DIR = Path(__file__).resolve().parent
INDEX_PATH = DATA_DIR / "vector_index.json"

CHUNK_SIZE = 500
CHUNK_OVERLAP = 80


# ---------------------------------------------------------------------------
# 임베딩
# ---------------------------------------------------------------------------

def _embed_openai(text: str, model: str = "text-embedding-3-small") -> list[float] | None:
    try:
        from openai import OpenAI
        api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("AZURE_OPENAI_API_KEY")
        base_url = os.environ.get("AZURE_OPENAI_ENDPOINT")
        if not api_key:
            return None
        client = OpenAI(api_key=api_key, base_url=base_url if base_url else None)
        resp = client.embeddings.create(input=[text], model=model)
        return resp.data[0].embedding
    except Exception:
        return None


def _embed_stub(text: str, dim: int = 128) -> list[float]:
    h = hash(text) & 0x7FFFFFFF
    return [((h * (i + 1) * 31) % 1000) / 1000.0 - 0.5 for i in range(dim)]


def embed_text(text: str) -> list[float]:
    vec = _embed_openai(text)
    return vec if vec is not None else _embed_stub(text)


# ---------------------------------------------------------------------------
# 청킹
# ---------------------------------------------------------------------------

def chunk_text(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> list[str]:
    if not text or not text.strip():
        return []
    text = text.strip()
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks = []
    current = []
    current_len = 0
    for p in paragraphs:
        p_len = len(p) + 2
        if current_len + p_len <= chunk_size:
            current.append(p)
            current_len += p_len
        else:
            if current:
                chunks.append("\n\n".join(current))
            if len(p) > chunk_size:
                start = 0
                while start < len(p):
                    end = start + chunk_size
                    chunks.append(p[start:end])
                    start = end - overlap
                current = []
                current_len = 0
            else:
                current = [p]
                current_len = p_len
    if current:
        chunks.append("\n\n".join(current))
    return [c for c in chunks if c.strip()]


# ---------------------------------------------------------------------------
# 인제스트
# ---------------------------------------------------------------------------

def ingest(
    base_dir: Path | None = None,
    metadata_filter: dict | None = None,
    out_path: Path | None = None,
) -> list[dict]:
    """
    Manifest 기준으로 문서 로드 → 청킹 → 임베딩 → 벡터 인덱스 저장.
    metadata_filter: 포함할 문서만 (예: {"status": "active"}).
    반환: 인덱스 항목 리스트 (id, path, metadata, chunk_index, content, vector).
    """
    base_dir = base_dir or DATA_DIR
    out_path = out_path or INDEX_PATH
    docs = get_documents(base_dir, metadata_filter=metadata_filter)
    indexed = []
    for doc in docs:
        chunks = chunk_text(doc["content"])
        for i, chunk in enumerate(chunks):
            vector = embed_text(chunk)
            indexed.append({
                "id": doc["id"],
                "path": doc["path"],
                "metadata": doc["metadata"],
                "chunk_index": i,
                "content": chunk,
                "vector": vector,
            })
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(indexed, f, ensure_ascii=False, indent=2)
    return indexed


# ---------------------------------------------------------------------------
# 검색
# ---------------------------------------------------------------------------

def _cosine_similarity(a: list[float], b: list[float]) -> float:
    import math
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def load_index(path: Path | None = None) -> list[dict]:
    p = path or INDEX_PATH
    if not p.exists():
        return []
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def search(
    query: str,
    k: int = 5,
    index: list[dict] | None = None,
    metadata_filter: dict | None = None,
) -> list[dict]:
    """
    쿼리와 유사한 청크 상위 k개 반환.
    metadata_filter가 있으면 해당 메타데이터를 만족하는 청크만 검색 (예: {"collection": "CAT-001"}).
    각 항목: { "id", "path", "metadata", "content", "score" }
    """
    index = index if index is not None else load_index()
    if not index:
        return []
    qvec = embed_text(query)
    scored = []
    for item in index:
        if metadata_filter and not metadata_matches(item.get("metadata") or {}, metadata_filter):
            continue
        score = _cosine_similarity(qvec, item["vector"])
        scored.append({
            "id": item["id"],
            "path": item["path"],
            "metadata": item.get("metadata"),
            "content": item.get("content"),
            "score": round(score, 4),
        })
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:k]


def route_category(
    query: str,
    categories: list[dict],
    index: list[dict] | None = None,
) -> str | None:
    """
    질의와 가장 관련 있는 카테고리 ID 하나 반환.
    categories: [ {"category_id", "category_name", "description"}, ... ] (schema.CATEGORIES 형태).
    각 카테고리의 (category_name + description)을 임베딩하고, query 임베딩과 유사도가 가장 높은 카테고리 반환.
    """
    if not categories:
        return None
    index = index if index is not None else load_index()
    qvec = embed_text(query)
    best_id = None
    best_score = -1.0
    for cat in categories:
        cid = cat.get("category_id")
        name = cat.get("category_name") or ""
        desc = cat.get("description") or ""
        text = f"{name}. {desc}".strip()
        if not text:
            continue
        cvec = embed_text(text)
        score = _cosine_similarity(qvec, cvec)
        if score > best_score:
            best_score = score
            best_id = cid
    return best_id


def search_in_stages(
    query: str,
    k: int = 5,
    categories: list[dict] | None = None,
    index: list[dict] | None = None,
) -> dict:
    """
    2단계 검색: (1) 질의가 5개 카테고리 중 어디에 해당하는지 결정 (route_category)
              (2) 해당 카테고리(collection) 청크만 metadata_filter로 걸러서 search.
    반환: { "collection": "CAT-001", "results": [ { "id", "path", "metadata", "content", "score" }, ... ] }
    categories가 None이면 schema.CATEGORIES 사용.
    """
    if categories is None:
        from data.schema import CATEGORIES
        categories = CATEGORIES
    index = index if index is not None else load_index()
    collection = route_category(query, categories, index=index)
    if not collection:
        results = search(query, k=k, index=index)
        return {"collection": None, "results": results}
    results = search(
        query, k=k, index=index,
        metadata_filter={"collection": collection},
    )
    return {"collection": collection, "results": results}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m data.rag index [key=value ...] | search <query> | search-stages <query>")
        return
    cmd = sys.argv[1].lower()
    if cmd == "index":
        metadata_filter = None
        for arg in sys.argv[2:]:
            if "=" in arg:
                if metadata_filter is None:
                    metadata_filter = {}
                k, v = arg.split("=", 1)
                metadata_filter[k.strip()] = v.strip()
        docs = get_documents(DATA_DIR, metadata_filter=metadata_filter)
        print(f"Documents from manifest (filter={metadata_filter}): {len(docs)}")
        indexed = ingest(metadata_filter=metadata_filter)
        print(f"Chunked & embedded: {len(indexed)} vectors -> {INDEX_PATH}")
    elif cmd == "search" and len(sys.argv) >= 3:
        query = " ".join(sys.argv[2:])
        results = search(query, k=5)
        print(f"Query: {query}\nTop {len(results)}:")
        for r in results:
            print(f"  [{r['score']}] id={r['id']} metadata={r.get('metadata')}")
            print(f"    {r['content'][:80]}...")
    elif cmd == "search-stages" and len(sys.argv) >= 3:
        query = " ".join(sys.argv[2:])
        out = search_in_stages(query, k=5)
        print(f"Query: {query}\nRouted collection: {out['collection']}\nTop {len(out['results'])}:")
        for r in out["results"]:
            print(f"  [{r['score']}] id={r['id']} metadata={r.get('metadata')}")
            print(f"    {r['content'][:80]}...")
    else:
        print("Usage: python -m data.rag index [key=value ...] | search <query> | search-stages <query>")


if __name__ == "__main__":
    main()
