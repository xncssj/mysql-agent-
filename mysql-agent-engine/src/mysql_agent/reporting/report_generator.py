"""Fault postmortem report generator."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class Evidence:
    timestamp: str
    category: str
    description: str
    raw_data: dict
    severity: str


@dataclass
class IncidentReport:
    instance_id: str
    time_window: tuple
    severity: str
    symptoms: List[str]
    timeline: List[dict]
    evidence_chain: List[Evidence]
    root_causes: List[dict]
    remediation: List[str]
    improvements: List[str]
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "instance_id": self.instance_id,
            "time_window": list(self.time_window),
            "severity": self.severity,
            "symptoms": self.symptoms,
            "timeline": self.timeline,
            "evidence_chain": [
                {
                    "timestamp": item.timestamp,
                    "category": item.category,
                    "description": item.description,
                    "severity": item.severity,
                }
                for item in self.evidence_chain
            ],
            "root_causes": self.root_causes,
            "remediation": self.remediation,
            "improvements": self.improvements,
            "generated_at": self.generated_at,
        }


REMEDIATION_MAP = {
    "RC01": "1. EXPLAIN 确认全表扫描\n2. 创建缺失索引\n3. ANALYZE TABLE 更新统计",
    "RC02": "1. SHOW ENGINE INNODB STATUS 分析死锁\n2. 找出长事务并 KILL\n3. 优化 SQL 减少锁范围",
    "RC03": "1. 检查 innodb_buffer_pool_size\n2. 建议调整为物理内存 60-70%\n3. 重启或在线调整",
    "RC07": "1. 查找长事务\n2. 拆分大事务\n3. 设置 innodb_lock_wait_timeout",
    "RC08": "1. SHOW SLAVE STATUS 检查延迟\n2. 检查从库 IO/CPU\n3. 考虑并行复制",
}


class ReportGenerator:
    """Generate structured incident reports from diagnosis results."""

    REPORT_TEMPLATE = """# MySQL 故障复盘报告

## 1. 基本信息
- **实例**: {instance_id}
- **时间窗口**: {time_start} ~ {time_end}
- **严重级别**: {severity}
- **报告生成**: {generated_at}

## 2. 现象描述
{symptoms}

## 3. 时间线
{timeline_table}

## 4. 证据链
{evidence_section}

## 5. 根因分析
{root_cause_section}

## 6. 解决方案
{remediation_section}

## 7. 后续改进
{improvements_section}
"""

    def __init__(self, prompt_builder: Optional[object] = None, rag_agent: Optional[object] = None):
        self.prompts = prompt_builder
        self.rag = rag_agent

    def generate(self, diagnosis_result: dict, instance_id: str) -> IncidentReport:
        evidence = self._collect_evidence(diagnosis_result)
        timeline = self._build_timeline(evidence)
        root_causes = diagnosis_result.get("root_causes", [])
        if not root_causes and diagnosis_result.get("top_root_cause"):
            root_causes = [
                {
                    "root_cause_id": diagnosis_result["top_root_cause"],
                    "name": diagnosis_result.get("summary", diagnosis_result["top_root_cause"]),
                    "score": 1.0,
                    "evidence": [],
                }
            ]

        return IncidentReport(
            instance_id=instance_id,
            time_window=(
                diagnosis_result.get("start", diagnosis_result.get("scan_time", "")),
                diagnosis_result.get("end", datetime.now().isoformat()),
            ),
            severity=self._calc_severity(diagnosis_result),
            symptoms=[item.get("description", str(item)) for item in diagnosis_result.get("anomalies", [])],
            timeline=timeline,
            evidence_chain=evidence,
            root_causes=root_causes,
            remediation=self._generate_remediation(root_causes),
            improvements=self._generate_improvements(diagnosis_result),
        )

    def render_markdown(self, report: IncidentReport) -> str:
        timeline_rows = "\n".join(
            f"| {event['time']} | {event['event']} | {event['severity']} |"
            for event in report.timeline
        )
        evidence_text = "\n".join(
            f"- **[{item.category}]** {item.description}" for item in report.evidence_chain
        )
        rc_text = "\n".join(
            f"### {rc.get('name', rc.get('root_cause_id', '未知'))} ({rc.get('root_cause_id', '')})\n"
            f"- 置信度: {rc.get('score', 0):.2f}\n"
            f"- 证据: {', '.join(rc.get('evidence', [])) or 'N/A'}"
            for rc in report.root_causes[:3]
        )
        return self.REPORT_TEMPLATE.format(
            instance_id=report.instance_id,
            time_start=report.time_window[0],
            time_end=report.time_window[1],
            severity=report.severity,
            generated_at=report.generated_at,
            symptoms="\n".join(f"- {symptom}" for symptom in report.symptoms) or "- 无",
            timeline_table=f"| 时间 | 事件 | 级别 |\n|------|------|------|\n{timeline_rows}",
            evidence_section=evidence_text or "- 无",
            root_cause_section=rc_text or "- 未识别到明确根因",
            remediation_section="\n".join(f"{idx + 1}. {step}" for idx, step in enumerate(report.remediation))
            or "- 待补充",
            improvements_section="\n".join(f"- [ ] {item}" for item in report.improvements),
        )

    def _collect_evidence(self, diagnosis: dict) -> List[Evidence]:
        evidence: List[Evidence] = []
        for anomaly in diagnosis.get("anomalies", []):
            evidence.append(
                Evidence(
                    timestamp=str(anomaly.get("timestamp", "")),
                    category="metric",
                    description=str(anomaly.get("description", anomaly.get("metric", ""))),
                    raw_data=anomaly,
                    severity=str(anomaly.get("severity", "WARNING")),
                )
            )
        for step in diagnosis.get("steps", []):
            evidence.append(
                Evidence(
                    timestamp=str(step.get("timestamp", "")),
                    category="diagnosis",
                    description=str(step.get("summary", step.get("tool", ""))),
                    raw_data=step,
                    severity="INFO",
                )
            )
        return evidence

    def _build_timeline(self, evidence: List[Evidence]) -> List[dict]:
        events = [
            {
                "time": item.timestamp or "unknown",
                "event": item.description,
                "severity": item.severity,
            }
            for item in evidence
        ]
        return sorted(events, key=lambda event: event["time"])

    def _calc_severity(self, diagnosis: dict) -> str:
        summary = diagnosis.get("summary", {})
        if isinstance(summary, dict) and summary.get("critical", 0) > 0:
            return "CRITICAL"
        if diagnosis.get("severity") == "CRITICAL":
            return "CRITICAL"
        return "WARNING"

    def _generate_remediation(self, root_causes: List[dict]) -> List[str]:
        steps: List[str] = []
        for rc in root_causes[:3]:
            rc_id = str(rc.get("root_cause_id", rc.get("name", "")))
            for key, action in REMEDIATION_MAP.items():
                if key in rc_id:
                    steps.append(action)
            for cmd in rc.get("verify_commands", []):
                steps.append(f"验证: {cmd}")
        return steps or ["继续观察相关指标并收集更多证据"]

    def _generate_improvements(self, diagnosis: dict) -> List[str]:
        return [
            "添加相关指标告警规则",
            "将本次 SQL 加入慢查询 Review 清单",
            "更新 Prompt Few-shot 示例库",
            "安排索引审计",
        ]
