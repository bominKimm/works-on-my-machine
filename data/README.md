# Knowledge Base (RAG용 데이터)

**manifest** 한 개로 “어떤 문서를 RAG에 넣을지”를 관리하는 구조입니다.

---

## 전체 과정이 뭐하는 건지

1. **문서 등록**  
   본문 텍스트 파일(`.txt` 등)을 `documents/` 같은 곳에 두고, **manifest.json**에 “문서 id, 파일 경로, 메타데이터”만 적어 둡니다.  
   → “이 경로의 이 파일을 하나의 문서로 쓴다”는 **목차**를 만드는 단계입니다.

2. **인제스트 (index)**  
   RAG가 **manifest만** 읽어서, 거기 적힌 경로의 파일들을 열고 → **코드로 청킹** → 임베딩 → `vector_index.json`에 저장합니다.  
   → “등록된 문서들을 잘게 쪼개서 벡터 DB에 넣는” 단계입니다.

3. **검색 (search)**  
   질의를 임베딩해서 벡터 인덱스에서 유사 청크를 찾고, 원본 문서 `id` / `metadata`와 함께 반환합니다.  
   → “넣어둔 지식에서 비슷한 내용 찾기” 단계입니다.

정리하면: **manifest = RAG에 넣을 문서 목록(목차)** 이고, 실제 본문은 **path**에 있는 파일입니다. 게시글 추가/삭제는 manifest에 항목만 추가/제거한 뒤 인제스트를 다시 돌리면 됩니다.

- **상세 흐름**(manifest 위치, 청크/벡터가 만들어지는 단계, active 필터 위치, 벡터 저장 위치): [FLOW.md](FLOW.md) 참고.

---

## Manifest 구조

`data/manifest.json` 한 파일이 **단일 진실 공급원**입니다. 형식은 아래처럼 **버전 + 문서 배열**입니다.

```json
{
  "version": "1.0",
  "documents": [
    {
      "id": "doc-001",
      "path": "documents/doc-001.txt",
      "metadata": {
        "status": "active",
        "collection": "policies",
        "version": "1.0"
      }
    },
    {
      "id": "doc-002",
      "path": "documents/faq/faq-01.txt",
      "metadata": {}
    }
  ]
}
```

| 필드 | 의미 |
|------|------|
| `version` | manifest 포맷 버전 (예: `"1.0"`) |
| `documents` | 문서 목록 (배열) |
| `documents[].id` | 문서 고유 id (추가/삭제/검색 결과에서 사용) |
| `documents[].path` | 본문 파일 경로 (data 폴더 기준 상대 경로) |
| `documents[].metadata` | 임의 key-value. 인제스트 시 **필터**에 사용 (예: `status=active`만 넣기) |

- **path**만 맞으면 폴더 구조는 자유입니다. `documents/a.txt`, `documents/정책/정책1.txt` 등 어떤 식이든 됩니다.
- **metadata**는 도메인에 따라 알아서 정하면 됩니다. (예: `status`, `collection`, `updated_at`)

---

## 디렉터리/파일 역할

| 파일/폴더 | 역할 |
|-----------|------|
| `manifest.json` | **문서 목차**: id, path, metadata 만 등록. RAG는 이것만 보고 어떤 파일을 넣을지 결정. |
| `documents/` | 실제 본문 텍스트 파일들 (path에 적힌 대로 둠) |
| `kb.py` | manifest 읽기/쓰기, `get_documents(metadata_filter)` 로 “필터 걸린 문서 목록 + 본문” 조회 |
| `rag.py` | manifest 기반으로 문서 로드 → 청킹 → 임베딩 → `vector_index.json` 저장 / 검색 |
| `vector_index.json` | `python -m data.rag index` 실행 시 생성 (청크별 벡터 + id, metadata) |
| `generate_dummy_data.py` | 예시 데이터 생성 (정책 도메인 예시로 manifest + documents 채움) |

---

## 실행 순서

```bash
# 1) 예시 manifest + 문서 생성 (카테고리별 LLM으로 가상 섹션 많이 생성)
#    OPENAI_API_KEY 또는 AZURE_OPENAI_API_KEY 있으면 LLM 호출, 없으면 schema 폴백
python -m data.generate_dummy_data

# 2) manifest에 등록된 문서 중 status=active 만 청킹·임베딩해 벡터 스토어에 저장
python -m data.rag index status=active

# 3) 검색
python -m data.rag search "DMZ 경유 규정"
```

- **OpenAI 키 연동**: 프로젝트 루트에 `.env` 파일을 두고 키를 넣으면 됩니다.  
  `cp .env.example .env` 후 `.env`에 `OPENAI_API_KEY` 또는 `AZURE_OPENAI_API_KEY`(·`AZURE_OPENAI_ENDPOINT`)를 채우면, `generate_dummy_data`·`rag index` 실행 시 자동으로 로드됩니다.
- **카테고리별 데이터를 많이 만들고 싶을 때**: 위처럼 `.env`에 키를 설정한 뒤 `generate_dummy_data`를 실행하면, 카테고리마다 LLM이 15개 섹션을 생성합니다. 키가 없으면 schema의 고정 콘텐츠 풀로 폴백합니다.

---

## 문서 추가/삭제

- **추가**: `documents/` 에 새 텍스트 파일 넣고, manifest의 `documents` 배열에 `{ "id", "path", "metadata" }` 한 줄 추가 → 다시 `rag index` 실행.
- **삭제**: manifest에서 해당 id 항목 제거 (또는 metadata에 `status: deprecated` 넣고 인제스트 시 `status=active`로 필터) → 다시 `rag index` 실행.

RAG 쪽은 **항상 manifest만** 보므로, 게시글/카테고리 구조가 바뀌어도 manifest와 path만 맞추면 재사용 가능합니다.
