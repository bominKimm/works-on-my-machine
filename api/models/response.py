from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "healthy"


class StepStatus(BaseModel):
    step: str
    status: str  # pending / in_progress / completed / error
    message: str = ""


class PolicyResult(BaseModel):
    status: str
    total_checks: int = 0
    violations: list[dict] = []
    recommendations: list[dict] = []
    summary: str = ""


class VulnerabilityItem(BaseModel):
    id: str
    severity: str
    category: str
    affected_resource: str
    title: str
    description: str
    evidence: str
    remediation: str
    benchmark_ref: str = ""


class AttackScenarioItem(BaseModel):
    id: str
    name: str
    mitre_technique: str
    target_vulnerabilities: list[str]
    severity: str
    prerequisites: str
    attack_chain: list[str]
    expected_impact: str
    detection_difficulty: str
    likelihood: str


class SecurityResult(BaseModel):
    vulnerabilities: list[VulnerabilityItem] = []
    attack_scenarios: list[AttackScenarioItem] = []
    vulnerability_summary: dict = {}
    report: str = ""


class AnalyzeResponse(BaseModel):
    status: str  # success / error
    task_id: str = ""
    steps: list[StepStatus] = []
    policy: PolicyResult | None = None
    security: SecurityResult | None = None
    error: str | None = None
