# 데이터 흐름

## 1. 파일 위치 정리

| 무엇 | 어디에 있음 |
|------|-------------|
| **manifest.json** | `data/manifest.json` (프로젝트의 `data` 폴더 바로 아래) |
| 문서 본문 텍스트 | `data/documents/...` (manifest의 `path`에 적힌 경로. 예: `documents/CAT-001/POST-SEC-2025-001/FILE-SEC-2025-001-V1.txt`) |
| **벡터 인덱스** (청크+임베딩) | `data/vector_index.json` |

- `manifest.json`은 **generate_dummy_data.py** 실행 시 생성됩니다.
- `vector_index.json`은 **python -m data.rag index** 실행 시 생성됩니다.

---

## 2. 전체 흐름 (한 번에)

```
[1] generate_dummy_data.py
    → categories.json, posts.json, files.json 생성
    → 카테고리별로 LLM으로 본문 생성
    → 각 "파일"마다 문서 1개 → data/documents/<경로>.txt 저장
    → manifest.json 생성 (각 문서의 id, path, metadata 기록)

[2] manifest.json (data/manifest.json)
    = "RAG에 넣을 문서 목록"
    - documents[]: id, path, metadata (여기에 status: "active" 등)

[3] python -m data.rag index status=active
    → kb.get_documents(data 폴더, metadata_filter={"status": "active"})
    → manifest를 읽고, metadata가 status=active 인 항목만 골라서
    → 각 항목의 path 파일을 열어 content 로드
    → 문서별로 chunk_text(content) → 청크 리스트
    → 청크마다 embed_text() → 벡터
    → 모든 청크를 { id, path, metadata, chunk_index, content, vector } 형태로
    → data/vector_index.json 에 저장

[4] python -m data.rag search "질의"
    → vector_index.json 로드
    → 질의를 임베딩 → 각 청크 벡터와 유사도 계산 → 상위 k개 반환
```

---

## 3. manifest.json이 있는 곳과 역할

- **위치**: `data/manifest.json` (data 폴더 루트)
- **역할**: "이 id의 문서는 **이 path**에 있고, metadata는 이거다" 목록. **본문 내용은 담지 않는다.**  
  RAG 인제스트 시에는 manifest로 **대상 문서 목록**(id, path, metadata)만 정하고, 실제 본문은 **각 path에 있는 파일을 열어** `kb.get_documents()`가 읽어 온 뒤 청킹·임베딩해 vector_index에 넣는다.  
  즉, "어떤 문서를 인덱스에 넣을지"는 manifest(+ metadata_filter)로 결정하고, "그 문서의 내용"은 해당 path의 .txt 파일에서 읽는다.
- **생성**: `generate_dummy_data.py`가 문서들을 쓴 뒤 `kb.save_manifest()`로 저장.

---

## 4. 데이터가 청크로 바뀌는 곳

- **진입점**: `rag.ingest()` (또는 CLI `python -m data.rag index`)
- **순서**:
  1. `kb.get_documents(base_dir, metadata_filter)` → manifest에서 필터 맞는 문서만 골라, 각 path 파일을 읽어 `[{ id, path, metadata, content }, ...]` 반환.
  2. 문서마다 `rag.chunk_text(doc["content"])` → 한 문서가 여러 개의 **문자열 청크**로 쪼개짐 (크기·겹침은 CHUNK_SIZE, CHUNK_OVERLAP).
  3. 각 청크마다 `rag.embed_text(chunk)` → **벡터** 생성.
  4. `{ id, path, metadata, chunk_index, content, vector }` 형태로 리스트에 넣어서 `data/vector_index.json`에 저장.

즉, **청크는 RAG 코드(rag.py) 안에서** 만들고, **임베딩된 벡터는 vector_index.json**에 들어갑니다.

---

## 5. 임베딩된 벡터는 어디에 저장되는지

- **파일**: `data/vector_index.json`
- **내용**: 위에서 만든 청크 단위 레코드 배열. 각 레코드에 `vector`(float 배열)와 `content`, `id`, `metadata` 등이 함께 저장됨.  
  **`content`**: 원본 문서 본문을 청킹해서 잘라 낸 **한 덩어리 텍스트 그대로** (요약·카테고리 설명 아님). 검색 시 이 문단을 에이전트/LLM 컨텍스트로 넣어 씀.
- **생성 시점**: `python -m data.rag index ...` 실행할 때마다 **전체 재생성** (지금 구현은 덮어쓰기).

---

## 6. active는 어디서 어떻게 필터링되는지

- **의미**: "이 문서를 RAG에 넣을지 말지"를 구분하는 값. manifest의 **metadata**에 `status: "active"` 처럼 들어 있음.
- **설정되는 곳**: `generate_dummy_data.py`가 manifest 항목을 만들 때, 각 문서의 `metadata`에 `status: "active"` 또는 `"deprecated"` 등을 넣음. (실제 값은 generator에서 정함.)
- **필터링되는 곳**: `rag index` 실행 시 CLI에서 `status=active` 같은 인자를 넘기면 → `metadata_filter = {"status": "active"}` → `kb.get_documents(..., metadata_filter=metadata_filter)` 호출 → **kb.py**의 `metadata_matches()`에서, manifest의 각 문서의 `metadata`가 `status: "active"`를 만족하는 것만 포함. 따라서 **active 필터링은 manifest를 읽을 때, kb.get_documents() 안**에서 이뤄짐.
- **대소문자**: 필터는 `metadata.status == "active"` 로 비교. `generate_dummy_data.py`는 manifest에 `status: "active"` / `"deprecated"`(소문자)로 넣음.

---

## 7. 검색 시 에이전트가 알 수 있는 것 (카테고리 등)

- `rag.search(query, k=5)` 반환값: 각 청크마다 `{ "id", "path", "metadata", "content", "score" }`.
- **metadata**는 인제스트 때 manifest에서 가져온 값이 그대로 들어 있음. 현재 `generate_dummy_data.py`가 넣는 항목은 `status`, **`collection`**(카테고리 ID, 예: `"CAT-001"`), `version`.
- 따라서 **에이전트가 추론할 때** 검색 결과의 `metadata["collection"]`을 보면 "이 청크가 어떤 카테고리(범주) 문서에서 왔는지" 알 수 있음. 카테고리 이름(예: "1. 정보보호 정책")이 필요하면 `categories.json` 또는 `schema.CATEGORIES`에서 `collection` ID로 매핑하면 됨.

---

## 8. 2단계 검색: 먼저 카테고리 결정 → 해당 카테고리 청크만 검색

- **목적**: 사용자 질의가 5개 카테고리 중 어디에 해당하는지 먼저 정한 뒤, 그 카테고리(collection)에 해당하는 청크에서만 벡터 검색해서, 불필요한 카테고리 청크가 결과에 섞이지 않게 함.
- **구현** (`data/rag.py`):
  1. **`route_category(query, categories)`**: 질의 문장을 임베딩하고, 각 카테고리의 `category_name`+`description`도 임베딩해서 유사도가 가장 높은 카테고리 ID(`collection`) 하나 반환. (vector_index의 벡터가 아니라, 카테고리 메타정보만으로 라우팅.)
  2. **`search(query, k, metadata_filter=...)`**: `metadata_filter`가 있으면 `vector_index.json`의 각 청크에서 `metadata`가 조건을 만족하는 것만 유사도 계산에 포함. 예: `metadata_filter={"collection": "CAT-001"}` → CAT-001 청크만 검색.
  3. **`search_in_stages(query, k)`**: 위 두 단계를 연속 호출. `route_category()`로 `collection` 결정 → `search(..., metadata_filter={"collection": collection})`로 해당 카테고리 청크만 검색. 반환: `{ "collection": "CAT-001", "results": [ ... ] }`.
- **사용 데이터**: 카테고리 목록은 `schema.CATEGORIES`(또는 호출 시 넘긴 `categories`). status·vector는 기존처럼 manifest·vector_index에서 사용. 즉, **status**는 인제스트 시 어떤 문서를 인덱스에 넣을지 정하고, **vector**는 청크별로 저장돼 있고, 2단계에서는 그 vector를 **특정 collection으로 필터한 뒤** 검색에만 씀.
- **CLI**: `python -m data.rag search-stages "질의"` 로 2단계 검색 동작 확인 가능.

---

## 9. 한 줄 요약

- **manifest.json** → `data/manifest.json` (문서 목록).
- **문서 본문** → manifest의 `path`가 가리키는 `data/documents/...` 텍스트 파일.
- **청크** → `rag.ingest()` 안에서 `chunk_text()`로 생성.
- **임베딩 벡터** → `rag.ingest()` 안에서 `embed_text()`로 만들고, **data/vector_index.json**에 저장.
- **active** → manifest의 `metadata.status`에 `"active"` 넣어 두고, `rag index status=active` 시 **kb.get_documents(metadata_filter)** 에서 걸러서 그 문서만 인제스트함.
- **검색 결과** → 각 항목에 `metadata`(예: `collection`, `status`, `version`) 포함 → 에이전트는 청크가 어느 카테고리 문서인지 추론 시 사용 가능.
- **2단계 검색** → `rag.search_in_stages(query)`: 질의로 카테고리 라우팅(`route_category`) 후, 해당 `collection` 청크만 `search(..., metadata_filter={"collection": ...})`로 검색.