# RAG를 통한 설계 보안 검토 데모

이 폴더는 **이미지 업로드 → Bicep 변환 → 사내 보안 정책(RAG)으로 위반 여부 검토**가 어떻게 동작하는지 예시로 보여줍니다.

## 흐름 요약

```
[사용자] 아키텍처 이미지 업로드
    → bicep_transformer: 이미지 → Bicep 코드
    → Policy Agent: Bicep + RAG(정책 문서) → 위반/권장 + 정책 근거(policy_ref)
```

1. **Bicep 코드**: 설계도가 Bicep 텍스트로 들어옵니다 (이미지면 AI Foundry 등으로 변환).
2. **참고 카테고리 선별**: design_review 시 **CAT-006(개발 설계 보안성 검토)** 은 항상 참고하고, Bicep에 포함된 리소스 유형(Storage, NSG, SQL, Key Vault, Web App 등)에 따라 **CAT-001~005 중 필요한 카테고리만** 추가로 선별합니다. (예: NSG 있으면 CAT-003, Storage 있으면 CAT-002·CAT-005.)
3. **RAG 검색**: 선별된 카테고리별로 **유사도 높은 정책 청크**를 가져와 병합합니다. CAT-006은 더 많이(예: 6개), 나머지 카테고리는 보조(예: 3개씩)로 가져와 문맥 길이를 맞춥니다.
4. **LLM 검토**: 가져온 정책 청크 + 참조 Bicep(정책 준수 예시) + **사용자 Bicep**을 LLM에 넘겨, 위반(violations)·권장(recommendations)과 **어느 정책에 근거한지(policy_ref)** 를 JSON으로 받습니다.

## 파일

| 파일 | 설명 |
|------|------|
| `sample_design.bicep` | 데모용 샘플 Bicep. 의도적으로 정책 위반을 넣어 둠 (NSG `*`, 스토리지 HTTP 허용, 웹앱 HTTPS 미설정 등). |
| `demo_rag_review.py` | 위 흐름을 로컬에서 재현하는 스크립트. RAG로 검색된 청크와 검토 결과를 출력합니다. |

## Bicep 변환 출력 샘플 (RedTeam Agent / Policy Agent 개발용)

`bicep_transformer`에서 나올 수 있는 아웃풋 형태의 예시 데이터. **총 16개.**

| 구분 | 개수 |
|------|------|
| **위반** | 13개 |
| **정상(준수)** | 2개 |
| **혼재** (일부만 위반) | 1개 |

### 전체 요약표

| No | 파일 | 위반/정상/혼재 | **상황 요약** | 구성 요약 | **위반 사항** |
|----|------|----------------|----------------|-----------|----------------|
| 01 | `sample_design.bicep` | 위반 | 데모용·다양한 위반 한꺼번에 포함 | NSG `*`, Storage HTTP·Blob 공개, Web TLS 1.0·FTP | NSG sourceAddressPrefix `*`; Storage supportsHttpsTrafficOnly false, allowBlobPublicAccess true; Web minTlsVersion 1.0, ftpsState AllAllowed |
| 02 | `bicep_sample_02_minimal_storage.bicep` | 위반 | 스토리지 단일 배포(최소 구성) | Storage 단일, HTTP·Blob 공개 | Storage supportsHttpsTrafficOnly false, allowBlobPublicAccess true |
| 03 | `bicep_sample_03_nsg_open_internet.bicep` | 위반 | VNet+NSG로 VM 접근만 열어둔 상황 | VNet+NSG, SSH/RDP/HTTP `*` | NSG sourceAddressPrefix `*` (SSH 22, RDP 3389, HTTP 80) |
| 04 | `bicep_sample_04_sql_open_firewall.bicep` | 위반 | SQL Server·DB만 배포, 방화벽 전부 개방 | SQL Server+DB, 방화벽 0.0.0.0–255.255.255.255 | SQL 방화벽 startIp 0.0.0.0, endIp 255.255.255.255 |
| 05 | `bicep_sample_05_keyvault_allow_network.bicep` | 위반 | Key Vault만 배포, 네트워크·퍼지 미설정 | Key Vault Allow, 퍼지 보호 없음 | KV networkAcls defaultAction Allow; enableSoftDelete false, enablePurgeProtection false |
| 06 | `bicep_sample_06_vm_public_rdp.bicep` | 위반 | VM 공용 IP·RDP·비밀번호 로그인 | VM+공용 IP, 비밀번호 인증, 디스크 암호화 없음 | VM 공용 IP 직접 연결; adminPassword 사용; osDisk 암호화 없음 |
| 07 | `bicep_sample_07_web_storage_compliant.bicep` | **정상** | 웹앱+스토리지, 정책 준수 구성 | NSG 제한, Storage HTTPS·TLS1.2, Web httpsOnly·TLS 1.2 | — |
| 08 | `bicep_sample_08_function_storage.bicep` | 위반 | Function+Storage 이벤트/파일 처리 | Function+Storage, TLS1.0, FTP AllAllowed | Storage minimumTlsVersion TLS1_0; Function ftpsState AllAllowed, minTlsVersion 1.0 |
| 09 | `bicep_sample_09_vnet_multi_tier.bicep` | 위반 | 3-tier(Web/App/DB) VNet 분리 구성 | 3-tier Web/App/DB, Web NSG `*` | Web NSG sourceAddressPrefix `*` (HTTPS 443) |
| 10 | `bicep_sample_10_mixed_resources.bicep` | 위반 | Storage·Key Vault·Web앱 혼합 한 번에 | Storage·KV·Web, Web HTTP·TLS1.0, KV Allow | Web httpsOnly false, minTlsVersion 1.0; KV networkAcls defaultAction Allow |
| 11 | `bicep_sample_11_api_management_backend.bicep` | 위반 | APIM으로 백엔드(App+Storage) 노출 | APIM+App+Storage(VNet Deny), NSG 관리 포트 `*` | NSG AllowManagement sourceAddressPrefix `*`, destinationPort 3443 |
| 12 | `bicep_sample_12_storage_private_endpoint_complex.bicep` | **정상** | Storage·KV Private Endpoint·VNet·DNS | Storage PE+Deny, KV Deny, VNet·Private DNS | — |
| 13 | `bicep_sample_13_frontdoor_web_storage_sql.bicep` | 위반 | Front Door+Web 2개+Storage+SQL 통합 | Front Door+Web 2개+Storage+SQL, HTTP·방화벽 개방 | Storage supportsHttpsTrafficOnly false, allowBlobPublicAccess true, minTls TLS1_0; Web httpsOnly false, minTls 1.0, ftpsState AllAllowed; SQL 방화벽 0.0.0.0 |
| 14 | `bicep_sample_14_event_driven_function_sb.bicep` | 위반 | Function+Service Bus+Logic App 이벤트 드리븐 | Function+Service Bus+Storage+Logic App, TLS1.0·FTP | Function ftpsState AllAllowed, minTlsVersion 1.0; Service Bus defaultAction Allow |
| 15 | `bicep_sample_15_data_platform_cosmos_sql_storage.bicep` | 위반 | 데이터 플랫폼(Cosmos+SQL+Storage+KV) | Cosmos+SQL+Storage+KV, SQL 방화벽 0–255·KV Allow | SQL 방화벽 0.0.0.0–255.255.255.255; KV networkAcls defaultAction Allow |
| 16 | `bicep_sample_16_storage_restricted_mixed.bicep` | 혼재 | 메인 Storage는 PE·캐시용은 공개 스토리지 혼용 | 메인 Storage 준수(PE+방화벽), 캐시 Storage 공개·HTTP | 캐시 Storage: supportsHttpsTrafficOnly false, allowBlobPublicAccess true, minTls TLS1_0, networkAcls defaultAction Allow |

---

## Policy Agent RAG: CAT-006 말고 다른 카테고리도 참고할 만한가?

**결론: 16개 Bicep 샘플 기준으로 CAT-001~005도 함께 참고하는 편이 좋다.**

- **CAT-006**은 “설계 검토용” 전용이라 **항상** 참고.
- 나머지 카테고리는 **Bicep에 들어 있는 리소스/키워드**에 따라 의미 있게 걸림.

| 카테고리 | 어떤 샘플에서 참고되기 좋은지 | 이유 |
|----------|------------------------------|------|
| **CAT-001** (정보보호 정책) | 05, 10, 11, 12, 15 | Key Vault, 암호화, 접근 통제·RBAC 관련 정책 |
| **CAT-002** (서비스구축 개발보안) | 01~16 거의 전부 | Storage·Web·SQL·Compute·API·설계 기준 – 대부분 샘플이 해당 리소스 포함 |
| **CAT-003** (하이브리드·네트워크) | 01, 03, 06, 07, 09, 11, 12, 16 | NSG, VNet, 서브넷, 방화벽 규칙 검토 시 필요 |
| **CAT-004** (개발환경·빌드) | 01, 03, 04, 09, 11, 13, 14, 15, 16 | `environment`·dev/staging/prod·배포 관련 정책 |
| **CAT-005** (운영·데이터 보안) | 02, 04, 06, 07, 08, 10, 12, 13, 14, 15, 16 | Storage·SQL·데이터·로그·백업 관련 정책 |

에이전트는 `data/categories.json`의 **design_review_keywords**로 “이 Bicep이 어떤 카테고리와 관련 있는지” 정한 뒤, **선별된 카테고리**에서만 RAG 검색하므로, 위 표처럼 CAT-001~005가 자연스럽게 섞여 들어가면 검토 품질이 좋아진다.

## 실행 방법

프로젝트 루트(`agenthon`)에서:

```bash
# 1) 벡터 인덱스 생성 (최초 1회 또는 정책 문서 갱신 후)
python -m data.rag index status=active

# 2) 데모 실행
python example/demo_rag_review.py
```

출력 예:

- **1단계**: `sample_design.bicep` 내용 일부
- **2단계**: Bicep 기반 선별 카테고리 (예: CAT-006, CAT-002, CAT-003, CAT-005) + 해당 카테고리에서 검색된 정책 청크 (출처 경로 + 내용)
- **3단계**: Policy Agent 검토 결과 (status, summary, violations, recommendations, policy_ref)

이를 통해 “Bicep 코드만 보고 RAG로 어떤 정책이 걸렸고, 그걸로 위반/권장이 어떻게 나오는지”를 확인할 수 있습니다.
