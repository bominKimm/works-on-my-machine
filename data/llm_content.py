"""
카테고리별 가상 문서 섹션을 LLM으로 생성.

API 키 필수. .env에 OPENAI_API_KEY 또는 AZURE_OPENAI_API_KEY를 넣어야 함.
없으면 키 입력을 요청하는 메시지 출력 후 종료.
"""

import json
import os
import sys

import data.env  # noqa: F401 - load .env before reading os.environ


def _require_api_key() -> str:
    """API 키가 있으면 반환, 없으면 안내 후 종료."""
    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("AZURE_OPENAI_API_KEY")
    if not api_key or not api_key.strip():
        print(
            "오류: API 키가 없습니다. .env 파일에 다음 중 하나를 설정해주세요.\n"
            "  OPENAI_API_KEY=sk-...\n"
            "  또는 AZURE_OPENAI_API_KEY=... (Azure OpenAI 사용 시 AZURE_OPENAI_ENDPOINT도 설정)\n"
            "프로젝트 루트의 .env.example을 참고하세요.",
            file=sys.stderr,
        )
        sys.exit(1)
    return api_key


def _call_llm(
    category_name: str,
    description: str,
    num_sections: int,
    document_theme: str | None = None,
    document_context: str | None = None,
) -> list[dict]:
    """
    OpenAI/Azure OpenAI로 섹션 N개 생성 요청.
    document_theme이 있으면 이 문서는 해당 주제 하나만 상세히 다룬다.
    """
    _require_api_key()
    from openai import OpenAI

    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("AZURE_OPENAI_API_KEY")
    base_url = os.environ.get("AZURE_OPENAI_ENDPOINT")
    client = OpenAI(api_key=api_key, base_url=base_url if base_url else None)
    model = os.environ.get("OPENAI_CHAT_MODEL", "gpt-4o-mini")

    theme_instruction = ""
    if document_theme:
        theme_instruction = f"""
[이 문서의 주제 (필수 준수)]
- **이 문서의 주제: {document_theme}**
- 위 주제에 대해서만 {num_sections}개 절을 작성하라. 다른 정책 유형을 한 문서에 나열하지 마라.
- 예: 주제가 "물리적 보안 정책"이면 출입 통제·CCTV·보안 구역·방문자 관리 등 그 주제 하위 내용만 자세히. "사이버 공격 대응 정책"이면 대응 절차·역할·기한·보고 체계만 자세히.
"""
    doc_hint = ""
    if document_context:
        doc_hint = f"\n- 문서 식별: {document_context}"

    prompt = f"""당신은 통신사 보안 담당이다. **한 편의 게시글 = 하나의 정책 주제만** 다룬다.

[원칙]
- 이 문서는 **단일 주제**만 다룬다. 여러 정책을 나열하지 말고, 정해진 주제에 대한 **상세 지침**만 쓴다.
- 카테고리: {category_name}. 설명: {description}.{doc_hint}
{theme_instruction}
[구조]
- chapter_level_1: 이 문서의 **주제(정책명)** 한 가지. 카테고리 이름(예: 정보보호 정책)을 절마다 반복하지 말고, 이 문서가 다루는 **구체 주제명**을 쓴다 (예: 물리적 보안 정책, 사이버 공격 대응 정책).
- chapter_level_2: 그 주제 안의 **소주제** (예: 출입 통제, CCTV 및 녹화, 초기 대응 절차).
- content: 그 소주제에 대한 **2~4문장의 구체적 지침**. 통신사 관점, 담당 부서·기한·기준·시행일 등 RAG로 검색해 쓸 만한 내용.

출력은 다음 JSON 배열 한 개만 (다른 말 없이).
[{{ "chapter_level_1": "이 문서의 정책명(단일 주제)", "chapter_level_2": "소주제", "content": "구체적 지침 2~4문장" }}, ...]
한글."""
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )
        text = (resp.choices[0].message.content or "").strip()
        if "```" in text:
            for part in text.split("```"):
                part = part.strip()
                if part.startswith("json"):
                    part = part[4:].strip()
                if part.startswith("["):
                    return json.loads(part)
        return json.loads(text)
    except Exception as e:
        print(
            f"API 호출 실패: {e}\n"
            "API 키(.env의 OPENAI_API_KEY 또는 AZURE_OPENAI_API_KEY)와 네트워크를 확인한 뒤 다시 시도해주세요.",
            file=sys.stderr,
        )
        sys.exit(1)


def generate_sections_for_category(
    category_id: str,
    category_name: str,
    description: str,
    num_sections: int = 15,
    document_theme: str | None = None,
    document_context: str | None = None,
) -> list[dict[str, str]]:
    """
    한 카테고리(및 선택적으로 한 문서)에 대해 LLM으로 섹션 리스트 생성.
    document_theme이 있으면 해당 주제 하나만 상세히 다룬 문서로 생성.
    """
    out = _call_llm(
        category_name, description, num_sections,
        document_theme=document_theme,
        document_context=document_context,
    )
    if not out or not isinstance(out, list):
        print("오류: LLM 응답 형식이 올바르지 않습니다. API 키와 네트워크를 확인한 뒤 다시 시도해주세요.", file=sys.stderr)
        sys.exit(1)
    return [
        {
            "chapter_level_1": str(x.get("chapter_level_1", "")),
            "chapter_level_2": str(x.get("chapter_level_2", "")),
            "content": str(x.get("content", "")),
        }
        for x in out
        if isinstance(x, dict)
    ]
