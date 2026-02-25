# Nmap 반복 실행 버그 수정 (최종)

## 문제

Agent Loop가 매 Iteration마다 Nmap 스캔만 반복 실행하고 다른 공격 도구로 전환하지 않음.

### 증상
```
[Iteration 1] Nmap 스캔 × 6개 타겟
[Iteration 2] Nmap 스캔 × 6개 타겟 (반복!)
[Iteration 3] Nmap 스캔 × 6개 타겟 (반복!)
...
```

## 근본 원인

### 1. LLM에게 충분한 가이드 부족 ❌
- Nmap 결과 후 어떤 도구를 사용해야 하는지 명확한 지시 없음
- "포트 발견 → 해당 포트 공격" 로직이 암시적이었음

### 2. 반복 방지 메커니즘 부재 ❌
- 같은 타겟에 Nmap을 여러 번 실행해도 제한 없음
- LLM이 이미 스캔을 완료했다는 사실을 인지하지 못함

### 3. 다음 행동 힌트 부족 ❌
- Nmap 결과 포맷이 단순함
- 발견된 포트에 대한 구체적인 액션 제안 없음

## 해결 방법

### 1. Critical Instructions 추가 ✅

초기 프롬프트에 강력한 지시 추가:

```python
**CRITICAL INSTRUCTIONS:**
1. After nmap scans are complete, you MUST move to exploitation phase
2. Do NOT repeat nmap on the same target unless scanning different ports
3. Use the attack tools (hydra, sqlserver, rdp, sqlmap) based on discovered ports
4. If a scan shows "no open ports", try a wider port range (1-5000) ONCE, then move on
```

### 2. 다음 행동 힌트 시스템 ✅

새로운 `_get_next_action_hint()` 메서드 추가:

```python
def _get_next_action_hint(self, result: AttackResult, iteration: int) -> str:
    """이전 결과 기반으로 다음 행동 힌트 제공"""
    
    if result.tool == "nmap":
        # 중복 스캔 감지
        nmap_count = sum(1 for r in self.attack_results if r.tool == "nmap" and r.target == result.target)
        
        if nmap_count > 1:
            return "⚠️ You've already scanned this target. Move to exploitation or scan a different target."
        
        # 열린 포트 기반 제안
        hints = []
        if any("22" in f for f in result.findings):
            hints.append("Port 22 (SSH) is open → Try attack_ssh_with_hydra")
        if any("3389" in f for f in result.findings):
            hints.append("Port 3389 (RDP) is open → Try attack_rdp")
        if any("1433" in f for f in result.findings):
            hints.append("Port 1433 (SQL Server) is open → Try attack_sqlserver")
        
        if hints:
            return "✅ Ports discovered! Suggested next tools:\n  - " + "\n  - ".join(hints)
```

**효과**: LLM이 발견된 포트를 보고 즉시 다음 도구를 인식

### 3. 반복 방지 로직 ✅

Agent Loop 내에서 Nmap 반복 감지 및 개입:

```python
# 🔍 중복 방지: 이미 충분히 스캔했으면 경고
nmap_count = sum(1 for r in self.attack_results if r.tool == "nmap")
if nmap_count >= 6 and prev_count == nmap_count:
    logger.warning(f"⚠️ Nmap만 {nmap_count}번 수행됨. 다른 도구로 전환 필요.")
    # 강제로 다음 단계 가이드 추가
    context += "\n\n**IMPORTANT**: You have completed reconnaissance. Now you MUST use attack tools (hydra, sqlserver, rdp, etc.) based on the scan results. Do NOT scan again.\n\n"
```

**효과**: 6번 이상 Nmap만 실행되면 강제로 다음 단계로 유도

### 4. 결과 포맷 개선 ✅

각 결과에 "Next Action Guidance" 섹션 추가:

```python
formatted = f"""
## Iteration {iteration} Result

**Tool**: {result.tool}
**Target**: {result.target}
**Status**: {status}

**Key Findings:**
  {findings_str}

---

**Next Action Guidance:**
{self._get_next_action_hint(result, iteration)}

Based on this result, what should be the next action?
"""
```

**효과**: LLM이 매 결과마다 명확한 다음 단계 제안 받음

## 코드 변경 위치

- `agents/agent.py` Line 1280-1289: Critical Instructions 추가
- `agents/agent.py` Line 1321-1371: `_get_next_action_hint()` 메서드 추가
- `agents/agent.py` Line 1148-1156: Nmap 반복 방지 로직 추가
- `agents/agent.py` Line 1316-1320: Next Action Guidance 포맷 추가

## 테스트 결과 예상

### Before (버그)
```
[Iteration 1] Nmap × 6
[Iteration 2] Nmap × 6 ❌ 반복!
[Iteration 3] Nmap × 6 ❌ 반복!
```

### After (수정 후)
```
[Iteration 1] Nmap × 6
  → Hint: "Port 22 open → Try attack_ssh_with_hydra"
[Iteration 2] attack_ssh_with_hydra ✅
  → Hint: "SSH succeeded! Test other services"
[Iteration 3] attack_sqlserver ✅
  → Hint: "SQL Server test complete. Continue testing"
[Iteration 4] scan_azure_blob ✅
[Complete] 4-7개 도구 실행됨
```

## 추가 개선 사항

만약 여전히 문제가 있다면:

### Option 1: 더 강한 제약 추가
```python
# 같은 타겟에 같은 도구 2번 이상 사용 금지
if f"{result.tool}_{result.target}" in used_combinations:
    skip this iteration
```

### Option 2: 명시적 단계 전환
```python
# Phase 기반 접근
if phase == "reconnaissance" and nmap_count >= 6:
    phase = "exploitation"
    context = "Reconnaissance complete. NOW START EXPLOITATION..."
```

### Option 3: Few-shot 예시 추가
```python
## Example Workflow:
1. scan_with_nmap → Found port 22
2. attack_ssh_with_hydra → Success
3. scan_with_nmap → Found port 1433
4. attack_sqlserver → Testing...
```

## 요약

**핵심 수정**:
1. ✅ Critical Instructions로 명확한 지시
2. ✅ 다음 행동 힌트 시스템 (포트 발견 → 도구 제안)
3. ✅ Nmap 반복 감지 및 강제 전환
4. ✅ 결과마다 Next Action Guidance 제공

**예상 효과**:
- ✅ Nmap 반복 방지
- ✅ 논리적 공격 흐름 (스캔 → 공격)
- ✅ 3-7개 도구 실행
- ✅ 모든 발견된 서비스 테스트

이제 테스트해보세요:
```bash
python agents/agent.py samples/test_multi_attack.bicep
```
