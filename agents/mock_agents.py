import asyncio


async def mock_policy_agent(bicep_code: str) -> dict:
    """
    Mock Policy Agent.

    실제 구현 예정:
    - MS Agent Framework 사용
    - Azure Policy 준수 여부 검증
    - 정책 위반 사항 상세 보고

    현재는 몇 가지 샘플 정책 검증 결과를 반환합니다.
    """
    # Policy 검증 시뮬레이션을 위한 지연
    await asyncio.sleep(0.8)

    # BiCep 코드에서 간단한 패턴 기반 검증 (Mock)
    violations = []
    recommendations = []

    if "Microsoft.Network/networkSecurityGroups" not in bicep_code:
        recommendations.append({
            "rule": "NSG-001",
            "severity": "medium",
            "message": "네트워크 보안 그룹(NSG) 리소스가 정의되지 않았습니다.",
            "recommendation": "모든 서브넷에 NSG를 연결하는 것을 권장합니다.",
        })

    if "'*'" in bicep_code and "sourceAddressPrefix" in bicep_code:
        violations.append({
            "rule": "NET-002",
            "severity": "high",
            "message": "네트워크 규칙에서 모든 소스 IP(*)를 허용하고 있습니다.",
            "recommendation": "특정 IP 대역으로 제한하세요.",
        })

    if "httpsOnly" not in bicep_code and "Microsoft.Web" in bicep_code:
        violations.append({
            "rule": "WEB-001",
            "severity": "high",
            "message": "웹 앱에 HTTPS 전용 설정이 누락되었습니다.",
            "recommendation": "httpsOnly: true를 설정하세요.",
        })

    if "minimumTlsVersion" not in bicep_code and "Microsoft.Storage" in bicep_code:
        recommendations.append({
            "rule": "STG-001",
            "severity": "medium",
            "message": "스토리지 계정에 최소 TLS 버전이 명시되지 않았습니다.",
            "recommendation": "minimumTlsVersion: 'TLS1_2'를 설정하세요.",
        })

    status = "failed" if violations else "passed"

    return {
        "status": status,
        "total_checks": 4,
        "violations": violations,
        "recommendations": recommendations,
        "summary": f"정책 검증 완료: {len(violations)}개 위반, {len(recommendations)}개 권장사항",
    }
