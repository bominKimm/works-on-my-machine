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

st.title("\U0001f6e1\ufe0f Azure 아키텍처 보안 검증")
st.caption("아키텍처 다이어그램을 업로드하면 자동으로 보안 취약점을 분석합니다.")

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
    run_btn = st.button("분석 시작", type="primary", disabled=uploaded_file is None, use_container_width=True)

# ---------------------------------------------------------------------------
# 분석 실행
# ---------------------------------------------------------------------------
if run_btn and uploaded_file is not None:
    # ---- 진행 상태 영역 ----
    st.subheader("분석 진행 상태")
    pipeline_steps = ["파일 업로드", "파일 전처리", "BiCep 변환", "Policy 검증", "RedTeam 분석"]
    progress_bar = st.progress(0)
    status_container = st.container()

    # 단계별 placeholder
    with status_container:
        step_cols = st.columns(len(pipeline_steps))
        step_placeholders = []
        for i, step_name in enumerate(pipeline_steps):
            with step_cols[i]:
                ph = st.empty()
                ph.markdown(f"**{step_name}**\n\n\u23f3 대기 중")
                step_placeholders.append(ph)

    # 업로드 표시
    step_placeholders[0].markdown("**파일 업로드**\n\n\u23f3 전송 중...")
    progress_bar.progress(10)

    # API 호출
    try:
        resp = requests.post(
            f"{API_BASE}/analyze",
            files={"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)},
            data={"skip_policy": str(skip_policy).lower()},
            timeout=120,
        )
        data = resp.json()
    except requests.ConnectionError:
        st.error("API 서버에 연결할 수 없습니다. `uvicorn api.main:app --port 8000` 으로 서버를 먼저 시작하세요.")
        st.stop()
    except Exception as e:
        st.error(f"API 호출 실패: {e}")
        st.stop()

    if data.get("status") == "error":
        st.error(f"분석 실패: {data.get('error')}")
        st.stop()

    # 단계별 결과 업데이트
    steps = data.get("steps", [])
    for i, step_name in enumerate(pipeline_steps):
        matched = next((s for s in steps if s["step"] == step_name), None)
        if matched and matched["status"] == "completed":
            msg = f"\u2705 {matched.get('message', '완료')}" if matched.get("message") else "\u2705 완료"
            step_placeholders[i].markdown(f"**{step_name}**\n\n{msg}")
        elif matched and matched["status"] == "error":
            step_placeholders[i].markdown(f"**{step_name}**\n\n\u274c 오류")
        progress_bar.progress(min(100, (i + 1) * 20))

    progress_bar.progress(100)

    st.divider()

    # ---- 결과 영역 ----
    security = data.get("security", {})
    policy = data.get("policy")
    vulns = security.get("vulnerabilities", [])
    attacks = security.get("attack_scenarios", [])
    vuln_summary = security.get("vulnerability_summary", {})

    # 요약 카드
    st.subheader("분석 요약")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("전체 취약점", len(vulns))
    c2.metric("Critical", vuln_summary.get("Critical", 0))
    c3.metric("High", vuln_summary.get("High", 0))
    c4.metric("Medium", vuln_summary.get("Medium", 0))
    c5.metric("공격 시나리오", len(attacks))

    st.divider()

    # 탭: 취약점 / 공격 시나리오 / Policy / 보고서
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
                color = {"Critical": "red", "High": "orange", "Medium": "blue", "Low": "green"}.get(v["severity"], "gray")
                with st.expander(f":{color}[**{v['severity']}**] {v['id']} - {v['title']}"):
                    st.markdown(f"**카테고리:** {v['category']}  \n**영향 리소스:** `{v['affected_resource']}`")
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
                color = {"Critical": "red", "High": "orange", "Medium": "blue", "Low": "green"}.get(atk["severity"], "gray")
                with st.expander(f":{color}[**{atk['severity']}**] {atk['id']} - {atk['name']}"):
                    st.markdown(f"**MITRE ATT&CK:** {atk['mitre_technique']}")
                    st.markdown(f"**탐지 난이도:** {atk['detection_difficulty']} | **발생 가능성:** {atk['likelihood']}")
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
            st.markdown(f"### {status_icon} 정책 검증 결과: **{policy['status'].upper()}**")
            if policy.get("violations"):
                st.markdown("#### 위반 사항")
                for v in policy["violations"]:
                    st.error(f"**[{v['rule']}] {v['severity'].upper()}** - {v['message']}  \n{v['recommendation']}")
            if policy.get("recommendations"):
                st.markdown("#### 권장 사항")
                for r in policy["recommendations"]:
                    st.warning(f"**[{r['rule']}] {r['severity'].upper()}** - {r['message']}  \n{r['recommendation']}")

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
# 초기 안내
# ---------------------------------------------------------------------------
elif not run_btn:
    st.info("왼쪽 사이드바에서 아키텍처 다이어그램 파일을 업로드하고 **분석 시작** 버튼을 누르세요.")

    with st.expander("지원하는 분석 파이프라인"):
        st.markdown("""
| 단계 | 설명 | 구현 상태 |
|------|------|-----------|
| 파일 업로드 | PDF, PNG, JPG 아키텍처 다이어그램 | UI |
| 파일 전처리 | 파일 파싱 및 Azure Blob 저장 | Mock |
| BiCep 변환 | 아키텍처 → BiCep 코드 변환 | Mock |
| Policy 검증 | Azure Policy 준수 여부 검증 | Mock |
| RedTeam 분석 | 취약점 탐지 + 공격 시뮬레이션 | Mock (정적 규칙) |
""")
