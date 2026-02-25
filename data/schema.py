"""
Semantic Guard Knowledge Base - 4-Tier 스키마 상수 및 콘텐츠 풀.

Policy Specialist 에이전트용 RAG/Vector DB 더미 데이터 생성에 사용.
- Layer 1: Category
- Layer 2: Post
- Layer 3: File
- Layer 4: Chunk
"""

from datetime import datetime

# ---------------------------------------------------------------------------
# Layer 1: Category
# ---------------------------------------------------------------------------
# design_review_keywords: 설계 보안성 검토 시 Bicep에 이 문자열이 있으면 이 카테고리 참고.
# generate_dummy_data가 categories.json을 쓸 때 이 값을 포함함. 에이전트는 categories.json(데이터)을
# 읽어 참고할 카테고리를 정함. CAT-006은 키워드 비어 있으면 "항상 참고"로 처리.
CATEGORIES = [
    {
        "category_id": "CAT-001",
        "category_name": "1. 정보보호 정책",
        "description": "전사 정보보호 및 개발보안 관련 기본 정책과 매뉴얼",
        "created_at": "2024-01-01T00:00:00Z",
        "design_review_keywords": ["KeyVault", "vaults", "Microsoft.KeyVault", "암호화", "접근 통제", "RBAC"],
    },
    {
        "category_id": "CAT-002",
        "category_name": "2. 서비스구축 개발보안",
        "description": "애플리케이션 개발 공통 설계 기준, 코딩 규칙, 배포 보안",
        "created_at": "2024-01-01T00:00:00Z",
        "design_review_keywords": ["Microsoft.Storage", "storageAccounts", "Microsoft.Web", "sites", "serverfarms", "Microsoft.Sql", "Microsoft.Compute", "virtualMachines", "API", "설계 기준"],
    },
    {
        "category_id": "CAT-003",
        "category_name": "3. 하이브리드 클라우드 및 네트워크",
        "description": "DMZ 구성, 단일 회선 금지, 온프레미스-클라우드 연동 보안",
        "created_at": "2024-01-01T00:00:00Z",
        "design_review_keywords": ["Microsoft.Network", "networkSecurityGroups", "virtualNetworks", "vnet", "subnets", "NSG", "방화벽"],
    },
    {
        "category_id": "CAT-004",
        "category_name": "4. 개발환경 및 빌드 보안",
        "description": "Dev/Staging 환경 IP·Proxy 관리, 상용망 접근 제한",
        "created_at": "2024-01-01T00:00:00Z",
        "design_review_keywords": ["environment", "dev", "staging", "prod", "deployment", "파이프라인"],
    },
    {
        "category_id": "CAT-005",
        "category_name": "5. 운영 및 데이터 보안",
        "description": "민감 데이터 반출, K-익명성, 합성 데이터 변환, 로그 보관",
        "created_at": "2024-01-01T00:00:00Z",
        "design_review_keywords": ["Microsoft.Storage", "storageAccounts", "Microsoft.Sql", "databases", "로그", "diagnostic", "백업"],
    },
    {
        "category_id": "CAT-006",
        "category_name": "6. 개발 설계 보안성 검토",
        "description": "개발자가 제출한 인프라·아키텍처 설계(Bicep 등)가 사내 보안 아키텍처 및 보안 정책에 위배되는지 검토하기 위한 기준. 네트워크, 스토리지, 웹앱, DB, Key Vault, VM, API·서버 접근 등 리소스별 필수·금지 사항",
        "created_at": "2024-01-01T00:00:00Z",
        "design_review_keywords": [],  # 항상 참고 (에이전트에서 항상 포함)
    },
]

# ---------------------------------------------------------------------------
# 카테고리별 보안 정책 주제 풀 (같은 카테고리 내 다양한 주제 – 문서마다 서로 다른 조합 사용)
# ---------------------------------------------------------------------------

# CAT-001: 정보보호 정책 – 다양한 정책 주제
CONTENT_POOL_CAT_001 = [
    {"chapter_level_1": "정보보호 기본 방침", "chapter_level_2": "적용 범위", "content": "본 정책은 전사 정보자산 및 개인정보를 다루는 모든 시스템과 개발·운영 프로세스에 적용된다. 외주 개발·하이브리드 클라우드 환경을 포함한다."},
    {"chapter_level_1": "정보보호 기본 방침", "chapter_level_2": "암호화 원칙", "content": "저장 및 전송 구간의 민감 정보는 AES-256 또는 동등 이상으로 암호화하고, 전송 시에는 TLS 1.2 이상을 의무 적용한다."},
    {"chapter_level_1": "접근 통제", "chapter_level_2": "접근 권한 관리", "content": "정보자산에 대한 접근은 업무 필요 최소 권한 원칙에 따라 부여하며, 정기적으로 권한 검토를 수행한다. 퇴직·전보 시 접근 권한은 즉시 회수한다."},
    {"chapter_level_1": "접근 통제", "chapter_level_2": "비밀번호 정책", "content": "비밀번호는 최소 8자 이상, 영문·숫자·특수문자 조합을 적용하고, 90일마다 변경을 권장한다. 다중 인증(MFA)은 관리자·원격 접속에 의무 적용한다."},
    {"chapter_level_1": "사고 대응", "chapter_level_2": "보안 사고 절차", "content": "보안 사고 발생 시 담당 부서는 초기 대응·포함·복구 절차에 따라 조치하고, 사후 원인 분석 및 재발 방지 대책을 수립·이행한다."},
    {"chapter_level_1": "자산 관리", "chapter_level_2": "정보자산 분류", "content": "정보자산은 민감도에 따라 분류하고, 등급별 저장·전송·폐기 절차를 적용한다. 중요 자산 목록은 정기적으로 갱신한다."},
    {"chapter_level_1": "개인정보 보호", "chapter_level_2": "수집·이용 최소화", "content": "개인정보는 수집 목적에 필요한 범위에서만 수집·이용하며, 보관 기간 경과 후 파기 또는 익명화한다. 제3자 제공 시 동의를 취득한다."},
    {"chapter_level_1": "백업 및 복구", "chapter_level_2": "백업 정책", "content": "중요 정보는 정기 백업을 수행하고, 백업본은 물리·지리적으로 분리 보관한다. 복구 훈련을 연 1회 이상 실시한다."},
    {"chapter_level_1": "로그 및 감사", "chapter_level_2": "로그 관리", "content": "시스템 접근·변경·오류 로그는 최소 1년 이상 보관하며, 무단 변경·삭제가 불가능한 방식으로 기록한다."},
    {"chapter_level_1": "물리 보안", "chapter_level_2": "출입 통제", "content": "중요 구역은 출입 통제를 적용하고, 출입 이력은 일정 기간 보관한다. 외부 인원 반입 시 사전 승인과 동행을 원칙으로 한다."},
    {"chapter_level_1": "외주 관리", "chapter_level_2": "외주 보안 요구사항", "content": "외주 개발·운영 시 계약에 보안 요구사항과 비밀 유지 조항을 포함하고, 납품 전 보안 검수를 수행한다."},
]

# CAT-002: 서비스구축 개발보안 – 다양한 개발보안 주제
CONTENT_POOL_CAT_002 = [
    {"chapter_level_1": "설계 기준", "chapter_level_2": "데이터 연동", "content": "내부 시스템 간 데이터 연동 시에는 암호화 통신(TLS 1.2 이상)을 적용하고, API 토큰은 하드코딩하지 않고 Vault 등에 보관한다."},
    {"chapter_level_1": "설계 기준", "chapter_level_2": "오류 처리", "content": "오류 메시지에는 스택 트레이스·내부 IP·DB 스키마 등을 노출하지 않고, 로그는 별도 보안 구간에서만 조회한다."},
    {"chapter_level_1": "코딩 규칙", "chapter_level_2": "입력값 검증", "content": "외부 입력(URL, 폼, API)은 화이트리스트 기반 검증 후 사용하며, SQL/NoSQL/OS 명령 삽입 방지를 위해 파라미터화된 쿼리만 사용한다."},
    {"chapter_level_1": "코딩 규칙", "chapter_level_2": "인증·세션", "content": "인증 실패 시 구체적 사유를 노출하지 않으며, 세션은 타임아웃·동시 로그인 정책을 적용한다. 중요 기능은 재인증을 요구한다."},
    {"chapter_level_1": "배포 보안", "chapter_level_2": "설정 관리", "content": "운영 환경 설정(DB 연결, API 키 등)은 코드 저장소에 포함하지 않고, 배포 파이프라인에서 주입한다."},
    {"chapter_level_1": "배포 보안", "chapter_level_2": "의존성 관리", "content": "라이브러리·이미지는 공식 또는 사내 허용 목록에서만 취득하고, CVE가 있는 버전은 빌드·배포에서 차단한다."},
    {"chapter_level_1": "API 보안", "chapter_level_2": "인증 및 권한", "content": "API는 인증(토큰·인증서 등) 후 호출 가능하도록 하고, 리소스별로 최소 권한을 부여한다. 비율 제한(Rate Limit)을 적용한다."},
    {"chapter_level_1": "API 보안", "chapter_level_2": "요청 검증", "content": "요청 크기·헤더·페이로드를 검증하고, 비정상 패턴은 차단·로그 기록한다."},
    {"chapter_level_1": "보안 테스트", "chapter_level_2": "정적·동적 분석", "content": "배포 전 정적 분석(SAST)·동적 분석(DAST)을 수행하고, 중대 결함은 해결 후 배포한다."},
]

# CAT-003: 하이브리드 클라우드 및 네트워크 – 다양한 네트워크/클라우드 보안 주제
CONTENT_POOL_CAT_003 = [
    {"chapter_level_1": "하이브리드 클라우드 설계", "chapter_level_2": "DMZ 경유 의무", "content": "온프레미스와 퍼블릭 클라우드 간 트래픽은 지정된 DMZ를 경유해야 하며, DMZ 우회 직접 회선은 금지한다."},
    {"chapter_level_1": "하이브리드 클라우드 설계", "chapter_level_2": "단일 회선 사용 금지", "content": "중요 구간에는 단일 회선 구성을 금지하고, 물리·논리 이중화(Active-Standby 등)를 적용한다."},
    {"chapter_level_1": "네트워크 세그멘테이션", "chapter_level_2": "서브넷 분리", "content": "웹·앱·DB tier는 서로 다른 서브넷에 두고, NSG로 최소 권한만 허용한다."},
    {"chapter_level_1": "네트워크 세그멘테이션", "chapter_level_2": "방화벽 정책", "content": "구간 간 방화벽은 기본 거부 후 필요한 트래픽만 허용하며, 규칙은 정기 검토한다."},
    {"chapter_level_1": "VPN 및 원격 접속", "chapter_level_2": "VPN 사용", "content": "원격 접속 시 사내 VPN 또는 인증된 채널을 사용하고, VPN 인증 정보는 강한 정책을 적용한다."},
    {"chapter_level_1": "클라우드 연동", "chapter_level_2": "연동 인증", "content": "온프레미스-클라우드 연동 시 서비스 계정·API 키는 최소 권한으로 부여하고, 주기적으로 갱신한다."},
    {"chapter_level_1": "트래픽 암호화", "chapter_level_2": "전송 암호화", "content": "구간 간 전송 데이터는 TLS 1.2 이상으로 암호화하고, 인증서는 유효 기간을 모니터링한다."},
]

# CAT-004: 개발환경 및 빌드 보안 – 다양한 개발환경 주제
CONTENT_POOL_CAT_004 = [
    {"chapter_level_1": "개발환경 보안", "chapter_level_2": "상용망 IP 하드코딩 금지", "content": "Dev/Staging 코드·설정에 상용망 IP·FQDN·연결 문자열을 하드코딩하지 않고, 환경변수 또는 설정 서버에서 주입한다."},
    {"chapter_level_1": "개발환경 보안", "chapter_level_2": "Proxy 사용", "content": "외부 API 호출 시 사내 Proxy를 사용하고, Proxy 인증 정보는 코드에 넣지 않고 시크릿 관리 도구에서 주입한다."},
    {"chapter_level_1": "빌드 및 배포", "chapter_level_2": "의존성 검증", "content": "빌드 시 라이브러리·이미지는 허용 목록에서만 취득하고, CVE 있는 버전은 파이프라인에서 차단한다."},
    {"chapter_level_1": "개발환경 보안", "chapter_level_2": "개발 PC 보안", "content": "개발 PC에는 필수 보안 에이전트·디스크 암호화를 적용하고, 업무 외 접속 제한 정책을 둔다."},
    {"chapter_level_1": "CI/CD 보안", "chapter_level_2": "파이프라인 자격 증명", "content": "CI/CD에서 사용하는 자격 증명은 파이프라인 전용으로 제한하고, 로그에 노출되지 않도록 한다."},
    {"chapter_level_1": "소스 코드 관리", "chapter_level_2": "저장소 보안", "content": "저장소 접근은 역할별로 제한하고, 민감 정보가 포함된 커밋은 차단·경고한다."},
]

# CAT-005: 운영 및 데이터 보안 – 다양한 운영/데이터 보안 주제
CONTENT_POOL_CAT_005 = [
    {"chapter_level_1": "민감 데이터 반출", "chapter_level_2": "위치·시간 결합 데이터", "content": "위치·시간이 결합된 개인 식별 가능 데이터를 외부 반출 시 K-익명성(k≥5 권장)을 만족하도록 비식별화한다."},
    {"chapter_level_1": "민감 데이터 반출", "chapter_level_2": "합성 데이터 변환", "content": "개발·테스트·분석용 개인정보는 가능한 경우 합성 데이터로 변환하고, 원본 반출을 최소화한다."},
    {"chapter_level_1": "로그 및 감사", "chapter_level_2": "로그 보관", "content": "접근·감사 로그는 최소 1년 이상 보관하고, 조회·반출 시 권한과 사유를 기록한다."},
    {"chapter_level_1": "데이터 분류", "chapter_level_2": "민감도별 처리", "content": "데이터는 민감도에 따라 분류하고, 저장·전송·폐기 시 등급별 절차를 적용한다."},
    {"chapter_level_1": "접근 로그", "chapter_level_2": "조회 이력", "content": "중요 데이터 조회 시 조회자·목적·범위를 기록하고, 비정상 조회는 알림한다."},
]

# CAT-006: 개발 설계 보안성 검토 – Bicep/인프라 설계 검토용 (Policy Agent RAG)
CONTENT_POOL_CAT_006 = [
    {"chapter_level_1": "개발 설계 보안성 검토 기준", "chapter_level_2": "적용 범위", "content": "본 기준은 개발자가 제출한 클라우드 인프라 설계(Bicep, ARM, 다이어그램 기반)가 사내 보안 아키텍처 및 정보보호 정책에 위배되지 않는지 검토할 때 적용한다. 데이터 스토리지, API 호출, 서버 접근, 네트워크 구간 설계가 모두 본 기준을 만족해야 한다."},
    {"chapter_level_1": "네트워크 보안 그룹(NSG)", "chapter_level_2": "소스·대상 주소 제한", "content": "NSG 규칙에서 sourceAddressPrefix 또는 destinationAddressPrefix에 '*'(모든 IP)를 사용하는 것은 금지한다. 관리·운영 구간은 사전 승인된 IP 대역 또는 VNet/서브넷만 허용하고, 최소 권한 원칙으로 규칙을 작성한다. SSH(22), RDP(3389)를 인터넷 전체에 열어두는 구성은 위반이다."},
    {"chapter_level_1": "네트워크 보안 그룹(NSG)", "chapter_level_2": "서브넷·티어 분리", "content": "웹·앱·DB tier는 반드시 서로 다른 서브넷에 두고, 각 구간에 NSG를 부착한다. DB tier는 웹/앱 tier와 필요한 포트만 허용하고, 인터넷 직접 접근은 금지한다."},
    {"chapter_level_1": "스토리지 계정", "chapter_level_2": "HTTPS 및 TLS", "content": "스토리지 계정은 supportsHttpsTrafficOnly를 true로 설정해야 한다. HTTP 트래픽 허용은 위반이다. minimumTlsVersion은 TLS1_2 이상으로 설정한다. 전송 구간 암호화는 전사 정책에 따라 TLS 1.2 이상 의무 적용이다."},
    {"chapter_level_1": "스토리지 계정", "chapter_level_2": "Blob 공개 접근", "content": "allowBlobPublicAccess는 보안 검토 없이 true로 두지 않는다. 기본값 false 또는 명시적 false를 권장하며, 공개 읽기가 필요한 경우 예외 승인 후 최소 범위로만 허용한다."},
    {"chapter_level_1": "웹 앱(App Service)", "chapter_level_2": "HTTPS 전용", "content": "App Service(웹앱)는 httpsOnly: true를 설정해야 한다. HTTP 허용은 위반이다. siteConfig 내 minTlsVersion은 '1.2' 이상으로 설정하고, ftpsState는 AllAllowed가 아닌 Disabled 또는 FtpsOnly로 제한한다."},
    {"chapter_level_1": "웹 앱(App Service)", "chapter_level_2": "TLS 버전", "content": "웹앱의 최소 TLS 버전은 1.2 이상이어야 한다. TLS 1.0/1.1은 사용 중단 정책에 따라 허용하지 않는다."},
    {"chapter_level_1": "SQL·데이터베이스", "chapter_level_2": "방화벽 규칙", "content": "SQL Server 방화벽 규칙에서 startIpAddress '0.0.0.0'과 endIpAddress '255.255.255.255'로 전체 인터넷을 허용하는 구성은 금지이다. 허용 IP는 사전 승인된 관리 구간·애플리케이션 서버 대역만 지정한다."},
    {"chapter_level_1": "SQL·데이터베이스", "chapter_level_2": "암호화 및 감사", "content": "민감 데이터를 다루는 SQL DB는 TDE(Transparent Data Encryption) 활성화를 권장하며, 감사(Auditing) 설정을 통해 접근·변경 이력을 남긴다. Azure AD 인증 사용을 권장한다."},
    {"chapter_level_1": "Key Vault", "chapter_level_2": "소프트 삭제 및 퍼지 보호", "content": "Key Vault는 enableSoftDelete를 true로, enablePurgeProtection를 true로 설정한다. 삭제 후 복구 가능 기간을 두고 퍼지 방지로 실수·악의적 삭제를 막는다."},
    {"chapter_level_1": "Key Vault", "chapter_level_2": "네트워크 제한", "content": "Key Vault의 networkAcls defaultAction은 Allow가 아닌 Deny를 원칙으로 하고, 허용된 VNet/서브넷 또는 IP만 bypass로 추가한다. 모든 네트워크에서 접근 허용은 위반이다."},
    {"chapter_level_1": "가상 머신·컴퓨팅", "chapter_level_2": "디스크 암호화", "content": "운영 VM의 OS 디스크 및 데이터 디스크는 암호화를 적용한다. Azure Disk Encryption 또는 플랫폼 관리 암호화를 사용하고, 설계도에 암호화 미적용은 검토 시 위반으로 지적한다."},
    {"chapter_level_1": "가상 머신·컴퓨팅", "chapter_level_2": "인증 방식", "content": "Linux VM은 비밀번호 인증보다 SSH 공개키 인증을 우선 적용한다. RDP/SSH를 0.0.0.0/0에 열어두는 설계는 금지이다."},
    {"chapter_level_1": "API·서버 접근", "chapter_level_2": "인증 및 최소 권한", "content": "API 및 내부 서버 접근은 인증(토큰, 인증서, Azure AD 등) 후에만 허용한다. 리소스별 최소 권한을 부여하고, 비율 제한(Rate Limit)을 적용한다. 하드코딩된 API 키·비밀번호는 금지이다."},
    {"chapter_level_1": "API·서버 접근", "chapter_level_2": "설정·시크릿 관리", "content": "DB 연결 문자열, API 키, 비밀번호는 코드·Bicep에 평문으로 넣지 않고 Key Vault 또는 파이프라인 시크릿에서 주입한다. @secure() 파라미터 사용을 권장한다."},
]

CONTENT_POOL_BY_CATEGORY = {
    "CAT-001": CONTENT_POOL_CAT_001,
    "CAT-002": CONTENT_POOL_CAT_002,
    "CAT-003": CONTENT_POOL_CAT_003,
    "CAT-004": CONTENT_POOL_CAT_004,
    "CAT-005": CONTENT_POOL_CAT_005,
    "CAT-006": CONTENT_POOL_CAT_006,
}

# 문서당 하나의 주제만 부여 (RAG: 한 문서 = 한 정책 주제, 상세 본문만)
DOCUMENT_THEMES_BY_CATEGORY = {
    "CAT-001": [
        "물리적 보안 정책",
        "사이버 공격 대응 정책",
        "접근 통제 정책",
        "암호화 및 키 관리 정책",
        "개인정보 보호 정책",
        "통신비밀 유지 정책",
        "네트워크 보안 정책",
        "보안 사고 대응 및 보고",
    ],
    "CAT-002": [
        "API 보안 설계 및 인증",
        "입력값 검증 및 인젝션 방지",
        "배포 파이프라인 보안",
        "의존성 및 CVE 관리",
        "설계 시 데이터 연동 보안",
    ],
    "CAT-003": [
        "DMZ 구성 및 경유 의무",
        "단일 회선 금지 및 이중화",
        "네트워크 세그멘테이션",
        "VPN 및 원격 접속 보안",
        "클라우드 연동 인증",
    ],
    "CAT-004": [
        "개발환경 상용망 접근 제한",
        "Proxy 및 환경변수 보안",
        "CI/CD 자격 증명 관리",
        "소스 코드 및 저장소 보안",
    ],
    "CAT-005": [
        "민감 데이터 반출 및 K-익명성",
        "합성 데이터 변환",
        "로그 보관 및 감사",
        "데이터 분류 및 접근 로그",
    ],
    "CAT-006": [
        "개발 설계 보안성 검토 기준 및 적용 범위",
        "NSG 및 네트워크 설계 검토",
        "스토리지·웹앱 TLS·HTTPS 검토",
        "SQL·Key Vault·VM 보안 설정 검토",
        "API 및 서버 접근·시크릿 관리 검토",
    ],
}

# 게시글/파일 생성을 위한 메타데이터 템플릿 (category_id → doc_type, title_prefix, file_prefix)
POST_TEMPLATES = {
    "CAT-001": [
        {"doc_type": "정책", "title_prefix": "[정책] 정보보호 기본방침", "file_prefix": "정보보호_기본방침"},
        {"doc_type": "매뉴얼", "title_prefix": "[매뉴얼] 암호화 적용 가이드", "file_prefix": "암호화_적용_가이드"},
    ],
    "CAT-002": [
        {"doc_type": "매뉴얼", "title_prefix": "[매뉴얼] 개발/서비스구축 개발보안", "file_prefix": "서비스구축_개발보안"},
        {"doc_type": "가이드", "title_prefix": "[가이드] API 보안 설계", "file_prefix": "API_보안_설계"},
    ],
    "CAT-003": [
        {"doc_type": "매뉴얼", "title_prefix": "[매뉴얼] 하이브리드 클라우드 네트워크", "file_prefix": "하이브리드클라우드_네트워크"},
        {"doc_type": "정책", "title_prefix": "[정책] DMZ 및 단일 회선 금지", "file_prefix": "DMZ_단일회선_정책"},
    ],
    "CAT-004": [
        {"doc_type": "매뉴얼", "title_prefix": "[매뉴얼] 개발환경 보안", "file_prefix": "개발환경_보안"},
        {"doc_type": "가이드", "title_prefix": "[가이드] Proxy 및 환경변수", "file_prefix": "Proxy_환경변수_가이드"},
    ],
    "CAT-005": [
        {"doc_type": "정책", "title_prefix": "[정책] 민감 데이터 반출", "file_prefix": "민감데이터_반출"},
        {"doc_type": "매뉴얼", "title_prefix": "[매뉴얼] K-익명성 및 합성데이터", "file_prefix": "K익명성_합성데이터"},
    ],
    "CAT-006": [
        {"doc_type": "가이드", "title_prefix": "[가이드] 개발 설계 보안성 검토", "file_prefix": "설계_보안성검토"},
        {"doc_type": "정책", "title_prefix": "[정책] 인프라 설계 보안 검토 기준", "file_prefix": "인프라_설계_검토기준"},
        {"doc_type": "매뉴얼", "title_prefix": "[매뉴얼] Bicep·클라우드 설계 정책 준수", "file_prefix": "Bicep_설계_정책준수"},
    ],
}

# 작성자 풀 (고정된 풀)
AUTHOR_NAMES = ["남현서","김남우","김소영","오승희","김보민"]
