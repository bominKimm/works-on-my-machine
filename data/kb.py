"""
범용 Knowledge Base 레이어: manifest 기반 문서 등록 및 조회.

- 단일 진실 공급원: manifest.json (문서 id, path, metadata 목록)
- 문서 본문은 path 기준으로 저장 (폴더 구조는 도메인 비의존)
- 추가/삭제: manifest 항목만 수정 후 재인제스트
"""

import json
from pathlib import Path
from typing import Any, Callable

MANIFEST_VERSION = "1.0"


def manifest_path(base_dir: Path) -> Path:
    return base_dir / "manifest.json"


def load_manifest(base_dir: Path) -> list[dict]:
    """
    manifest.json 로드.
    반환: [ { "id", "path", "metadata": {} }, ... ]
    """
    path = manifest_path(base_dir)
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("documents", [])


def save_manifest(base_dir: Path, documents: list[dict]) -> None:
    """manifest.json 저장."""
    path = manifest_path(base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"version": MANIFEST_VERSION, "documents": documents}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def metadata_matches(doc_meta: dict, filter_spec: dict | None) -> bool:
    """filter_spec의 모든 key=value가 doc_meta에 있으면 True."""
    if not filter_spec:
        return True
    return all(doc_meta.get(k) == v for k, v in filter_spec.items())


def get_documents(
    base_dir: Path,
    manifest_path_override: Path | None = None,
    metadata_filter: dict | Callable[[dict], bool] | None = None,
) -> list[dict]:
    """
    Manifest에서 문서 목록을 읽고, 본문을 로드해 반환.

    - base_dir: manifest와 path의 기준 디렉터리.
    - metadata_filter: 포함할 문서 필터.
      - dict면 해당 key=value가 metadata에 있는 항목만.
      - callable(metadata) -> bool 이면 True인 항목만.
    반환: [ { "id", "path", "metadata", "content" }, ... ]
    """
    base = base_dir
    manifest_file = manifest_path_override or base / "manifest.json"
    if not manifest_file.exists():
        return []
    data = json.loads(manifest_file.read_text(encoding="utf-8"))
    entries = data.get("documents", [])
    out = []
    for ent in entries:
        meta = ent.get("metadata") or {}
        if callable(metadata_filter):
            if not metadata_filter(meta):
                continue
        elif isinstance(metadata_filter, dict) and not metadata_matches(meta, metadata_filter):
            continue
        path = base / ent["path"] if not Path(ent["path"]).is_absolute() else Path(ent["path"])
        try:
            content = path.read_text(encoding="utf-8")
        except Exception:
            content = ""
        out.append({
            "id": ent["id"],
            "path": ent["path"],
            "metadata": meta,
            "content": content,
        })
    return out


def add_document(
    base_dir: Path,
    doc_id: str,
    relative_path: str,
    metadata: dict | None = None,
) -> None:
    """Manifest에 문서 한 건 추가 (이미 있으면 덮어쓰지 않고 무시)."""
    docs = load_manifest(base_dir)
    if any(d["id"] == doc_id for d in docs):
        return
    docs.append({
        "id": doc_id,
        "path": relative_path,
        "metadata": metadata or {},
    })
    save_manifest(base_dir, docs)


def remove_document(base_dir: Path, doc_id: str) -> bool:
    """Manifest에서 해당 id 제거. 반환: 제거 여부."""
    docs = load_manifest(base_dir)
    new_docs = [d for d in docs if d["id"] != doc_id]
    if len(new_docs) == len(docs):
        return False
    save_manifest(base_dir, new_docs)
    return True
