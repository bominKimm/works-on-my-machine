"""Azure 아키텍처 보안 검증 에이전트 - Streamlit UI."""

import requests
import streamlit as st

API_BASE = "http://localhost:8000/api/v1"

# ---------------------------------------------------------------------------
# 페이지 설정
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Azure Security Analyzer",
    page_icon="\U0001f6e1\ufe0f",
    layout="wide",
)

# st.title("\U0001f6e1\ufe0f Azure 아키텍처 보안 검증")
# st.caption("아키텍처 다이어그램을 업로드하면 자동으로 보안 취약점을 분석합니다.")

# ---------------------------------------------------------------------------
# 세션 상태 초기화
# ---------------------------------------------------------------------------
if "analysis_result" not in st.session_state:
    st.session_state.analysis_result = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# ---------------------------------------------------------------------------
# 사이드바 - 파일 업로드
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("파일 업로드")
    uploaded_file = st.file_uploader(
        "아키텍처 다이어그램",
        type=["pdf", "png", "jpg", "jpeg"],
        help="PDF, PNG, JPG 형식 지원 (최대 20MB)",
    )
    skip_policy = st.checkbox("Policy 검증 건너뛰기", value=False)
    run_btn = st.button(
        "분석 시작",
        type="primary",
        disabled=uploaded_file is None,
        use_container_width=True,
    )


# ---------------------------------------------------------------------------
# 파이프라인 트리 HTML 생성
# ---------------------------------------------------------------------------
def _pipeline_html(steps_data: dict | None = None) -> str:
    """헥사곤 노드 + SVG 분기/합류 화살표로 파이프라인 트리 렌더링."""
    BLUE = "#1a73e8"
    PURPLE = "#7c3aed"
    GREEN = "#16a34a"
    AMBER = "#d97706"
    PENDING = "#94a3b8"
    ERROR = "#dc2626"

    def _state(name: str) -> str:
        if not steps_data:
            return "pending"
        return steps_data.get(name, {}).get("status", "pending")

    def _msg(name: str) -> str:
        if not steps_data:
            return ""
        m = steps_data.get(name, {}).get("message", "") or ""
        return (m[:22] + "…") if len(m) > 22 else m

    def _color(name: str, active: str) -> str:
        s = _state(name)
        if s in ("completed", "in_progress"):
            return active
        if s == "error":
            return ERROR
        return PENDING

    def _icon(name: str) -> str:
        return {"completed": "✅", "error": "❌", "in_progress": "🔄"}.get(
            _state(name), "⏳"
        )

    def _hex_node(name: str, active: str, size: int = 100) -> str:
        c = _color(name, active)
        inner = int(size * 0.86)
        label = name.replace(" ", "<br>")
        msg = _msg(name)
        msg_html = (
            f'<div style="font-size:7.5px;color:#475569;margin-top:2px;line-height:1.2;">{msg}</div>'
            if msg
            else ""
        )
        return (
            f'<div title="{name}" style="'
            f"clip-path:polygon(50% 0%,100% 25%,100% 75%,50% 100%,0% 75%,0% 25%);"
            f"background:{c};width:{size}px;height:{size}px;"
            f'display:flex;align-items:center;justify-content:center;flex-shrink:0;">'
            f'<div style="'
            f"clip-path:polygon(50% 0%,100% 25%,100% 75%,50% 100%,0% 75%,0% 25%);"
            f"background:#fff;width:{inner}px;height:{inner}px;"
            f"display:flex;flex-direction:column;"
            f"align-items:center;justify-content:center;text-align:center;"
            f'padding:4px;box-sizing:border-box;">'
            f'<span style="font-size:16px;line-height:1;">{_icon(name)}</span>'
            f'<span style="font-size:8.5px;font-weight:700;color:{c};'
            f'line-height:1.3;margin-top:2px;">{label}</span>'
            f"{msg_html}"
            f"</div></div>"
        )

    def _arrow(from_name: str, active: str) -> str:
        c = _color(from_name, active)
        return (
            f'<div style="display:flex;align-items:center;flex-shrink:0;padding:0 4px;">'
            f'<div style="width:32px;height:2px;background:{c};"></div>'
            f'<div style="width:0;height:0;'
            f"border-top:5px solid transparent;border-bottom:5px solid transparent;"
            f'border-left:9px solid {c};"></div>'
            f"</div>"
        )

    # --- 노드 ---
    s1 = _hex_node("파일 업로드", BLUE)
    s2 = _hex_node("파일 전처리", BLUE)
    s3 = _hex_node("BiCep 변환", BLUE)
    p1 = _hex_node("Policy 검증", PURPLE, 90)
    p2 = _hex_node("RedTeam 분석", GREEN, 90)
    s5 = _hex_node("결과 종합", AMBER)

    a1 = _arrow("파일 업로드", BLUE)
    a2 = _arrow("파일 전처리", BLUE)

    pc = _color("Policy 검증", PURPLE)
    rc = _color("RedTeam 분석", GREEN)
    bc = _color("BiCep 변환", BLUE)
    fc = _color("결과 종합", AMBER)

    # --- 분기 SVG (BiCep → 병렬) ---
    branch_svg = (
        f'<svg width="90" height="220" style="flex-shrink:0;overflow:visible;">'
        f"<defs>"
        f'<marker id="mp" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto">'
        f'<path d="M0,0 L0,6 L8,3 z" fill="{pc}"/></marker>'
        f'<marker id="mr" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto">'
        f'<path d="M0,0 L0,6 L8,3 z" fill="{rc}"/></marker>'
        f"</defs>"
        f'<line x1="0"  y1="110" x2="30"  y2="110" stroke="{bc}" stroke-width="2.5"/>'
        f'<line x1="30" y1="45"  x2="30"  y2="175" stroke="#e2e8f0" stroke-width="2"/>'
        f'<line x1="30" y1="45"  x2="82"  y2="45"  stroke="{pc}" stroke-width="2.5" marker-end="url(#mp)"/>'
        f'<line x1="30" y1="175" x2="82"  y2="175" stroke="{rc}" stroke-width="2.5" marker-end="url(#mr)"/>'
        f"</svg>"
    )

    # --- 합류 SVG (병렬 → 결과 종합) ---
    merge_svg = (
        f'<svg width="90" height="220" style="flex-shrink:0;overflow:visible;">'
        f"<defs>"
        f'<marker id="mf" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto">'
        f'<path d="M0,0 L0,6 L8,3 z" fill="{fc}"/></marker>'
        f"</defs>"
        f'<line x1="0"  y1="45"  x2="60" y2="45"  stroke="{pc}" stroke-width="2.5"/>'
        f'<line x1="0"  y1="175" x2="60" y2="175" stroke="{rc}" stroke-width="2.5"/>'
        f'<line x1="60" y1="45"  x2="60" y2="175" stroke="#e2e8f0" stroke-width="2"/>'
        f'<line x1="60" y1="110" x2="82" y2="110" stroke="{fc}" stroke-width="2.5" marker-end="url(#mf)"/>'
        f"</svg>"
    )

    parallel_col = (
        f'<div style="display:flex;flex-direction:column;gap:40px;flex-shrink:0;">'
        f"{p1}{p2}"
        f"</div>"
    )

    inner_row = (
        f'<div style="display:flex;align-items:center;gap:0;min-width:820px;padding:20px 15px;">'
        f"{s1}{a1}{s2}{a2}{s3}{branch_svg}{parallel_col}{merge_svg}{s5}"
        f"</div>"
    )

    return (
        f'<div style="'
        f"background:#f8fafc;border:1px solid #e2e8f0;border-radius:16px;"
        f"padding:24px 20px;margin:8px 0;overflow-x:auto;"
        f"font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;\">"
        f"{inner_row}"
        f"</div>"
    )


# ---------------------------------------------------------------------------
# 요약 카드 (전체 너비)
# ---------------------------------------------------------------------------
def _render_summary(data: dict) -> None:
    security = data.get("security", {})
    vulns = security.get("vulnerabilities", [])
    attacks = security.get("attack_scenarios", [])
    vuln_summary = security.get("vulnerability_summary", {})

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("전체 취약점", len(vulns))
    c2.metric("Critical", vuln_summary.get("Critical", 0))
    c3.metric("High", vuln_summary.get("High", 0))
    c4.metric("Medium", vuln_summary.get("Medium", 0))
    c5.metric("공격 시나리오", len(attacks))


# ---------------------------------------------------------------------------
# 결과 탭 (왼쪽 컬럼)
# ---------------------------------------------------------------------------
def _render_tabs(data: dict) -> None:
    security = data.get("security", {})
    policy = data.get("policy")
    vulns = security.get("vulnerabilities", [])
    attacks = security.get("attack_scenarios", [])

    tab_vuln, tab_attack, tab_policy, tab_report = st.tabs(
        ["취약점 목록", "공격 시뮬레이션", "Policy 검증", "보고서"]
    )

    # -- 취약점 탭 --
    with tab_vuln:
        if not vulns:
            st.info("발견된 취약점이 없습니다.")
        else:
            severity_filter = st.multiselect(
                "심각도 필터",
                ["Critical", "High", "Medium", "Low"],
                default=["Critical", "High", "Medium", "Low"],
            )
            for v in vulns:
                if v["severity"] not in severity_filter:
                    continue
                color = {
                    "Critical": "red",
                    "High": "orange",
                    "Medium": "blue",
                    "Low": "green",
                }.get(v["severity"], "gray")
                with st.expander(
                    f":{color}[**{v['severity']}**] {v['id']} - {v['title']}"
                ):
                    st.markdown(
                        f"**카테고리:** {v['category']}  \n**영향 리소스:** `{v['affected_resource']}`"
                    )
                    st.markdown(f"**설명:** {v['description']}")
                    st.markdown(f"**수정 방법:** {v['remediation']}")
                    if v.get("benchmark_ref"):
                        st.markdown(f"**벤치마크:** {v['benchmark_ref']}")

    # -- 공격 시나리오 탭 --
    with tab_attack:
        if not attacks:
            st.info("도출된 공격 시나리오가 없습니다.")
        else:
            for atk in attacks:
                color = {
                    "Critical": "red",
                    "High": "orange",
                    "Medium": "blue",
                    "Low": "green",
                }.get(atk["severity"], "gray")
                with st.expander(
                    f":{color}[**{atk['severity']}**] {atk['id']} - {atk['name']}"
                ):
                    st.markdown(f"**MITRE ATT&CK:** {atk['mitre_technique']}")
                    st.markdown(
                        f"**탐지 난이도:** {atk['detection_difficulty']} | **발생 가능성:** {atk['likelihood']}"
                    )
                    st.markdown(f"**전제 조건:** {atk['prerequisites']}")
                    st.markdown("**공격 체인:**")
                    for step in atk["attack_chain"]:
                        st.markdown(f"- {step}")
                    st.markdown(f"**예상 피해:** {atk['expected_impact']}")

    # -- Policy 탭 --
    with tab_policy:
        if policy is None:
            st.info("Policy 검증을 건너뛰었습니다.")
        else:
            status_icon = "\u2705" if policy["status"] == "passed" else "\u274c"
            st.markdown(
                f"### {status_icon} 정책 검증 결과: **{policy['status'].upper()}**"
            )
            if policy.get("violations"):
                st.markdown("#### 위반 사항")
                for v in policy["violations"]:
                    st.error(
                        f"**[{v['rule']}] {v['severity'].upper()}** - {v['message']}  \n{v['recommendation']}"
                    )
            if policy.get("recommendations"):
                st.markdown("#### 권장 사항")
                for r in policy["recommendations"]:
                    st.warning(
                        f"**[{r['rule']}] {r['severity'].upper()}** - {r['message']}  \n{r['recommendation']}"
                    )

    # -- 보고서 탭 --
    with tab_report:
        report_md = security.get("report", "")
        if report_md:
            st.download_button(
                "보고서 다운로드 (.md)",
                data=report_md,
                file_name="security_report.md",
                mime="text/markdown",
                use_container_width=True,
            )
            st.divider()
            st.markdown(report_md)
        else:
            st.info("보고서가 생성되지 않았습니다.")


# ---------------------------------------------------------------------------
# 챗봇 (오른쪽 컬럼)
# ---------------------------------------------------------------------------
def _render_chatbot(data: dict) -> None:
    st.subheader("AI 보안 어드바이저")
    st.caption("왼쪽 결과를 보면서 질문하세요.")

    # 스크롤 가능한 대화 영역
    msg_box = st.container(height=520)
    with msg_box:
        if not st.session_state.chat_history:
            st.markdown(
                "<div style='color:#94a3b8;font-size:14px;text-align:center;padding:40px 0;'>"
                "분석 결과에 대해 궁금한 점을 질문하세요.<br>"
                "<span style='font-size:12px;'>예: Critical 취약점 수정 우선순위는?</span>"
                "</div>",
                unsafe_allow_html=True,
            )
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    # 입력창
    if prompt := st.chat_input("질문을 입력하세요...", key="chat_input"):
        st.session_state.chat_history.append({"role": "user", "content": prompt})

        with msg_box:
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                with st.spinner("분석 중..."):
                    try:
                        resp = requests.post(
                            f"{API_BASE}/chat",
                            json={
                                "question": prompt,
                                "context": {
                                    "security": data.get("security"),
                                    "policy": data.get("policy"),
                                },
                                "history": st.session_state.chat_history[:-1],
                            },
                            timeout=120,
                        )
                        resp.raise_for_status()
                        answer = resp.json().get("answer") or "응답을 받지 못했습니다."
                    except requests.ConnectionError:
                        answer = "API 서버에 연결할 수 없습니다."
                    except Exception as e:
                        answer = f"오류: {e}"

                st.markdown(answer)

        st.session_state.chat_history.append({"role": "assistant", "content": answer})


# ---------------------------------------------------------------------------
# 분석 실행
# ---------------------------------------------------------------------------
pipeline_ph = None

if run_btn and uploaded_file is not None:
    st.session_state.chat_history = []
    st.session_state.analysis_result = None

    st.subheader("분석 진행 상태")
    pipeline_ph = st.empty()
    pipeline_ph.markdown(
        _pipeline_html(
            {"파일 업로드": {"status": "in_progress", "message": "전송 중..."}}
        ),
        unsafe_allow_html=True,
    )

    try:
        resp = requests.post(
            f"{API_BASE}/analyze",
            files={
                "file": (
                    uploaded_file.name,
                    uploaded_file.getvalue(),
                    uploaded_file.type,
                )
            },
            data={"skip_policy": str(skip_policy).lower()},
            timeout=120,
        )
        data = resp.json()
    except requests.ConnectionError:
        st.error(
            "API 서버에 연결할 수 없습니다. `uvicorn api.main:app --port 8000` 으로 서버를 먼저 시작하세요."
        )
        st.stop()
    except Exception as e:
        st.error(f"API 호출 실패: {e}")
        st.stop()

    if data.get("status") == "error":
        st.error(f"분석 실패: {data.get('error')}")
        st.stop()

    st.session_state.analysis_result = data
    steps_data = {s["step"]: s for s in data.get("steps", [])}
    pipeline_ph.markdown(_pipeline_html(steps_data), unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# 결과 화면 (분석 완료 후 항상 유지)
# ---------------------------------------------------------------------------
_data = st.session_state.analysis_result

if _data is not None and _data.get("status") != "error":
    # 파이프라인: 분석 직후가 아닐 때만 새로 렌더링
    if pipeline_ph is None:
        st.subheader("분석 진행 상태")
        steps_data = {s["step"]: s for s in _data.get("steps", [])}
        st.markdown(_pipeline_html(steps_data), unsafe_allow_html=True)

    st.divider()

    # 요약 메트릭 (전체 너비)
    st.subheader("분석 요약")
    _render_summary(_data)

    st.divider()

    # 결과 탭(왼쪽) | 챗봇(오른쪽) 분할 레이아웃
    col_left, col_right = st.columns([55, 45], gap="large")

    with col_left:
        st.subheader("상세 분석 결과")
        _render_tabs(_data)

    with col_right:
        _render_chatbot(_data)

# ---------------------------------------------------------------------------
# 초기 안내
# ---------------------------------------------------------------------------
elif not run_btn and _data is None:
    st.info(
        "왼쪽 사이드바에서 아키텍처 다이어그램 파일을 업로드하고 **분석 시작** 버튼을 누르세요."
    )

    with st.expander("지원하는 분석 파이프라인"):
        st.markdown(
            """
| 단계 | 설명 | 실행 방식 | 구현 상태 |
|------|------|-----------|-----------|
| 파일 업로드 | PDF, PNG, JPG 아키텍처 다이어그램 | 순차 | UI |
| 파일 전처리 | 파일 파싱 및 Azure Blob 저장 | 순차 | Mock |
| BiCep 변환 | 아키텍처 → BiCep 코드 변환 | 순차 | Mock |
| Policy 검증 | Azure Policy 준수 여부 검증 | **병렬** | Mock |
| RedTeam 분석 | 취약점 탐지 + 공격 시뮬레이션 | **병렬** | Mock (정적 규칙) |
| 결과 종합 | 전체 결과 집계 및 AI 어드바이저 활성화 | 순차 | 자동 |

> Policy 검증과 RedTeam 분석은 BiCep 변환 완료 후 동시에 실행되며, 둘 다 완료되면 결과 종합 단계가 진행됩니다.
"""
        )
