# Agent Loop 조기 종료 버그 수정

## 문제 분석

Agent Loop가 Nmap 스캔만 수행하고 종료하는 버그가 발견되었습니다.

### 증상
1. Iteration 1에서 6개 타겟에 대해 nmap 스캔 수행
2. 모든 스캔이 성공으로 표시됨
3. Iteration 2에서 LLM이 "no open ports on any targets" 응답
4. LLM이 "COMPLETE" 선언하며 종료
5. 추가 공격 도구(Hydra, SQLMap 등) 미실행

### 근본 원인

#### 1. 프롬프트에 새 도구 누락 ❌
- 초기 컨텍스트에 4개 도구만 명시 (Nmap, Hydra(SSH), SQLMap, Metasploit)
- 새로 추가한 3개 도구 누락:
  - attack_sqlserver
  - attack_rdp
  - scan_azure_blob
- LLM이 사용 가능한 도구를 인식하지 못함

#### 2. LLM에게 전달되는 정보 부족 ❌
- Nmap 결과에서 findings만 전달 (최대 5개)
- raw_output이 포함되지 않아 LLM이 상세 정보 확인 불가
- 포트가 발견되어도 LLM이 적절한 다음 도구를 선택하지 못함

#### 3. 가이드라인 부족 ❌
- LLM에게 포트 발견 시 어떤 도구를 사용할지 명확한 가이드 없음
- "포트 22 → attack_ssh_with_hydra" 같은 매핑 정보 부재

## 수정 사항

### 1. 프롬프트에 모든 7개 도구 명시 ✅

```python
## Available Tools

You have access to the following penetration testing tools:
1. **scan_with_nmap**: Port scanning and service detection (use this FIRST)
2. **attack_ssh_with_hydra**: SSH brute force attack (use after finding port 22)
3. **attack_sql_with_sqlmap**: SQL injection testing (use for web applications)
4. **exploit_with_metasploit**: Exploit known vulnerabilities
5. **attack_sqlserver**: SQL Server authentication brute force (use after finding port 1433) ← NEW
6. **attack_rdp**: RDP brute force attack (use after finding port 3389) ← NEW
7. **scan_azure_blob**: Azure Blob storage public access scan (use for storage accounts) ← NEW
```

### 2. 포트-도구 매핑 가이드 추가 ✅

```python
2. **Analysis**: Based on scan results, identify potential vulnerabilities:
   - Port 22 (SSH) → use attack_ssh_with_hydra
   - Port 1433 (SQL Server) → use attack_sqlserver
   - Port 3389 (RDP) → use attack_rdp
   - Port 80/443 (Web) → use attack_sql_with_sqlmap
   - Storage accounts → use scan_azure_blob
```

### 3. Raw Output 미리보기 추가 ✅

```python
# Nmap 결과에 raw_output의 처음 500자 포함
if result.tool == "nmap" and result.raw_output:
    raw_preview = f"\n\n**Raw Output Preview:**\n```\n{result.raw_output[:500]}\n```\n"
```

LLM이 실제 Nmap 출력을 보고 열린 포트를 확인할 수 있음.

### 4. Nmap 파싱 개선 ✅

```python
def _parse_nmap_output(self, output: str) -> List[str]:
    # 디버깅 로그 추가
    logger.debug(f"Nmap raw output:\n{output}")
    
    # 결과 메시지 개선
    if not findings:
        if "Nmap done" in output or "Host is up" in output:
            return ["Host is up, but no open ports found in scanned range"]
        else:
            return ["Scan failed or incomplete - no results"]
```

### 5. Findings 개수 증가 ✅

```python
findings_str = "\n  ".join(result.findings[:10])  # 5 → 10개로 증가
```

더 많은 정보를 LLM에게 제공.

### 6. 가이드라인 강화 ✅

```python
## Important Guidelines

- **Always start with nmap** to understand the attack surface
- **Scan a wider port range** if initial scan finds nothing (e.g., 1-5000)
- **Test each discovered service** with appropriate attack tools
- **Use tools sequentially** based on previous results
- **Target one service at a time** for focused testing
- **Explain your reasoning** before each tool call
- **Say "COMPLETE"** only after thoroughly testing all targets and services
```

## 코드 변경 위치

- `agents/agent.py` Line 1241-1274: 초기 컨텍스트 프롬프트 업데이트
- `agents/agent.py` Line 1277-1315: _format_tool_result() - raw_output 미리보기 추가
- `agents/agent.py` Line 1722-1750: _parse_nmap_output() - 파싱 개선 및 디버깅

## 테스트 방법

```bash
# 수정된 Agent 실행
python agents/agent.py samples/test_multi_attack.bicep

# 예상 결과:
# [Iteration 1] Nmap 스캔 (6개 타겟)
# [Iteration 2] LLM이 열린 포트 확인 (raw_output 보고 판단)
# [Iteration 3] attack_sqlserver 또는 attack_ssh_with_hydra 실행
# [Iteration 4-6] 추가 공격 도구 실행
# [Iteration 7+] 모든 타겟 테스트 후 COMPLETE
```

## 예상 효과

- ✅ LLM이 모든 7개 도구 인식
- ✅ Nmap 결과 기반으로 적절한 다음 도구 선택
- ✅ 포트-도구 매핑으로 논리적 공격 흐름
- ✅ 조기 종료 방지 (모든 타겟 테스트 후 종료)
- ✅ 3-7개 도구 실행 (Nmap + 발견된 서비스별 공격)

## 추가 디버깅 옵션

만약 여전히 문제가 발생하면:

1. **로그 레벨 증가**
```python
# 파일 상단에 추가
logging.basicConfig(level=logging.DEBUG)
```

2. **Raw Nmap 출력 확인**
- Nmap raw_output이 실제로 열린 포트를 보고하는지 확인
- Docker 컨테이너가 실제로 포트를 expose하는지 확인

3. **LLM 응답 전체 로깅**
```python
# run_agent_loop에서 response 전체 출력
logger.info(f"Full LLM response: {response}")
```
