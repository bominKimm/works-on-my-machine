# 보안 도구 설치 가이드 (macOS)

## 현재 상태
- ✅ Docker: 설치됨 및 실행 중
- ❌ Nmap: 미설치
- ❌ Hydra: 미설치
- ❌ SQLMap: 미설치
- ❌ Metasploit: 미설치

---

## 빠른 설치 (추천)

### 1. Nmap 설치 (필수)
```bash
brew install nmap
```

**설치 후 확인:**
```bash
nmap --version
```

### 2. Hydra 설치 (선택적)
```bash
brew install hydra
```

**설치 후 확인:**
```bash
hydra -h | head -5
```

### 3. SQLMap 설치 (선택적)
```bash
brew install sqlmap
```

**설치 후 확인:**
```bash
sqlmap --version
```

### 4. Metasploit 설치 (고급, 선택적)
Metasploit은 크기가 크고 설치가 복잡합니다. 기본 테스트에는 불필요합니다.

```bash
# 방법 1: Homebrew (간단하지만 최신 버전 아님)
brew install metasploit

# 방법 2: 공식 인스톨러 (권장)
# https://docs.metasploit.com/docs/using-metasploit/getting-started/nightly-installers.html
curl https://raw.githubusercontent.com/rapid7/metasploit-omnibus/master/config/templates/metasploit-framework-wrappers/msfupdate.erb > msfinstall
chmod +x msfinstall
./msfinstall
```

---

## 단계별 설치 및 테스트

### Step 1: Nmap만 설치 (가장 기본적)
```bash
brew install nmap
```

그런 다음 Agent 실행:
```bash
python agents/agent.py samples/sample_bicep.bicep
```

**예상 결과**: Nmap은 실제 스캔, 나머지는 Mock

---

### Step 2: Nmap + Hydra 설치 (인증 테스트 포함)
```bash
brew install nmap hydra
```

**예상 결과**: Nmap과 Hydra는 실제 실행

---

### Step 3: 전체 설치 (완전한 침투 테스트)
```bash
brew install nmap hydra sqlmap
# Metasploit은 선택사항
```

---

## Docker를 사용한 실제 배포

현재는 `use_docker=False`로 설정되어 Mock 컨테이너를 사용합니다.

### Docker 모드 활성화

**방법 1: 커맨드라인 수정**
```python
# agents/agent.py 마지막 부분 수정
if __name__ == "__main__":
    # ... (기존 코드)
    
    # 수정: use_docker=True로 변경
    async def main():
        agent = LocalAttackAgent(use_docker=True)  # 여기!
        # ...
```

**방법 2: Python 스크립트로 실행**
```python
import asyncio
from agents.agent import LocalAttackAgent

async def main():
    # Docker 사용
    agent = LocalAttackAgent(use_docker=True)
    
    with open('samples/sample_bicep.bicep', 'r') as f:
        bicep_code = f.read()
    
    result = await agent.analyze_and_attack(bicep_code)
    
    if result['success']:
        print(f"✅ 공격 완료: {result['attacks_executed']}개")
        
        # 보고서 저장
        with open('attack_report.md', 'w') as f:
            f.write(result['report'])
    
    # 중요: Docker 컨테이너 정리
    agent.cleanup()

asyncio.run(main())
```

---

## 설치 시간 예상

| 도구 | 설치 시간 | 용량 | 필요성 |
|------|-----------|------|--------|
| Nmap | 1-2분 | ~20MB | ⭐⭐⭐ 필수 |
| Hydra | 1-2분 | ~5MB | ⭐⭐ 권장 |
| SQLMap | 1-2분 | ~10MB | ⭐ 선택 |
| Metasploit | 10-20분 | ~200MB | 선택 (고급) |

---

## 빠른 테스트 (Nmap만으로)

가장 빠르게 실제 동작을 보려면:

```bash
# 1. Nmap만 설치
brew install nmap

# 2. Agent 실행
cd /Users/soyeong/Desktop/kt/ms-agenthon/works-on-my-machine
source .venv/bin/activate
python agents/agent.py samples/sample_bicep.bicep
```

**예상 출력 변화:**
```
Before:
2026-02-24 17:09:16,923 - __main__ - WARNING - Nmap 미설치, Mock 결과 반환

After:
2026-02-24 17:09:16,923 - __main__ - INFO - Nmap 스캔 시작: 172.20.0.10
[실제 nmap 실행 중...]
2026-02-24 17:09:21,456 - __main__ - INFO - Nmap 결과: 실제 스캔 완료
```

---

## 주의사항

⚠️ **보안 도구 사용 시 주의**
1. **로컬 테스트만**: 절대 실제 프로덕션 시스템에 사용하지 마세요
2. **권한 필요**: 일부 도구는 관리자 권한이 필요할 수 있습니다
3. **방화벽 경고**: macOS 방화벽에서 네트워크 접근 허용 확인
4. **윤리적 사용**: 허가 없이 타인의 시스템을 스캔하지 마세요

---

## 문제 해결

### Homebrew 설치 오류
```bash
# Homebrew 업데이트
brew update

# 권한 문제 시
sudo chown -R $(whoami) /usr/local/Homebrew
```

### Docker 컨테이너 충돌
```bash
# 기존 attack_network 컨테이너 정리
docker network ls | grep attack
docker network rm attack_network

# 모든 컨테이너 정리
docker-compose down -v
```

### 도구 실행 권한 오류
```bash
# nmap에 권한 부여 (필요 시)
sudo chmod +x /usr/local/bin/nmap
```

---

## 권장 설치 순서

**초보자 (10분)**:
```bash
brew install nmap
```

**중급자 (15분)**:
```bash
brew install nmap hydra sqlmap
```

**고급자 (30분)**:
```bash
brew install nmap hydra sqlmap metasploit
```

---

## 다음 단계

1. ✅ 이 가이드를 따라 도구 설치
2. ✅ Agent 다시 실행
3. ✅ 로그에서 "실제 실행" 확인
4. ✅ 생성된 보고서 확인

설치 후 문제가 발생하면 알려주세요!
