"""Golden set evaluation runner."""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from ..agents.explain_agent import ExplainDiagnosisAgent
from ..agents.index_agent import IndexAdvisorAgent
from ..agents.sql_rewriter import SQLRewriterAgent
from ..agents.root_cause_agent import RootCauseAgent
from ..agents.cross_correlation_agent import CrossCorrelationAgent
from ..agents.deadlock_agent import DeadlockAgent
from ..agents.replication_agent import ReplicationAgent


SCHEMA_PATH = Path(__file__).resolve().parents[3] / "data/schema/ecommerce.json"


@dataclass
class EvalCaseResult:
    case_id: str
    task: str
    passed: bool
    message: str
    details: Dict[str, Any] = field(default_factory=dict)


def load_golden_set(path: str | Path) -> List[Dict[str, Any]]:
    cases: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                cases.append(json.loads(line))
    return cases


def evaluate_explain_case(case: Dict[str, Any], agent: ExplainDiagnosisAgent) -> EvalCaseResult:
    payload = case["input"]
    expected = case["expected"]
    result = agent.diagnose(payload["sql"], payload["explain"])
    findings = result.findings

    found_rule_ids = {finding.rule_id for finding in findings}
    expected_rules = [item["rule_id"] for item in expected.get("findings", [])]
    missing = [rule_id for rule_id in expected_rules if rule_id not in found_rule_ids]

    level_checks = []
    for item in expected.get("findings", []):
        if "level" not in item:
            continue
        matched = next((finding for finding in findings if finding.rule_id == item["rule_id"]), None)
        if matched and matched.level != item["level"]:
            level_checks.append(f"{item['rule_id']} expected level {item['level']} got {matched.level}")

    min_findings = expected.get("min_findings", len(expected_rules))
    passed = not missing and not level_checks and len(findings) >= min_findings
    message = "ok"
    if missing:
        message = f"missing rules: {', '.join(missing)}"
    elif level_checks:
        message = "; ".join(level_checks)
    elif len(findings) < min_findings:
        message = f"findings count {len(findings)} < min_findings {min_findings}"

    return EvalCaseResult(
        case_id=case["id"],
        task=case["task"],
        passed=passed,
        message=message,
        details={
            "found_rule_ids": sorted(found_rule_ids),
            "expected_rule_ids": expected_rules,
            "summary": result.summary,
        },
    )


def evaluate_index_case(case: Dict[str, Any], agent: IndexAdvisorAgent) -> EvalCaseResult:
    payload = case["input"]
    expected = case["expected"]
    result = agent.advise(
        sql=payload["sql"],
        table=payload["table"],
        explain=payload.get("explain"),
    )

    found_rule_ids = {finding.rule_id for finding in result.findings}
    expected_rule = expected.get("rule_id")
    missing_rule = expected_rule and expected_rule not in found_rule_ids

    ddl_text = " ".join(result.ddl_suggestions).lower()
    missing_tokens = [
        token.lower()
        for token in expected.get("ddl_contains", [])
        if token.lower() not in ddl_text
    ]

    passed = not missing_rule and not missing_tokens
    message = "ok"
    if missing_rule:
        message = f"missing rule: {expected_rule}"
    elif missing_tokens:
        message = f"ddl missing tokens: {', '.join(missing_tokens)}"

    return EvalCaseResult(
        case_id=case["id"],
        task=case["task"],
        passed=passed,
        message=message,
        details={
            "found_rule_ids": sorted(found_rule_ids),
            "expected_rule_id": expected_rule,
            "ddl_suggestions": result.ddl_suggestions,
            "summary": result.summary,
        },
    )


def evaluate_rewrite_case(case: Dict[str, Any], agent: SQLRewriterAgent) -> EvalCaseResult:
    payload = case["input"]
    expected = case["expected"]
    result = agent.rewrite(payload["sql"])

    found_rule_ids = {finding.rule_id for finding in result.findings}
    expected_rule = expected.get("rule_id")
    missing_rule = expected_rule and expected_rule not in found_rule_ids

    rewrite_text = result.rewritten_sql.lower()
    missing_tokens = [
        token.lower()
        for token in expected.get("rewrite_contains", [])
        if token.lower() not in rewrite_text
    ]

    passed = not missing_rule and not missing_tokens
    message = "ok"
    if missing_rule:
        message = f"missing rule: {expected_rule}"
    elif missing_tokens:
        message = f"rewrite missing tokens: {', '.join(missing_tokens)}"

    return EvalCaseResult(
        case_id=case["id"],
        task=case["task"],
        passed=passed,
        message=message,
        details={
            "found_rule_ids": sorted(found_rule_ids),
            "expected_rule_id": expected_rule,
            "rewritten_sql": result.rewritten_sql,
            "summary": result.summary,
        },
    )


def evaluate_root_cause_case(case: Dict[str, Any], agent: RootCauseAgent) -> EvalCaseResult:
    payload = case["input"]
    expected = case["expected"]
    result = agent.diagnose(payload["anomalies"])

    passed = (
        result.top_root_cause == expected.get("top_root_cause")
        and result.cross_pattern == expected.get("cross_pattern")
    )
    message = "ok"
    if result.top_root_cause != expected.get("top_root_cause"):
        message = f"top_root_cause expected {expected.get('top_root_cause')} got {result.top_root_cause}"
    elif result.cross_pattern != expected.get("cross_pattern"):
        message = f"cross_pattern expected {expected.get('cross_pattern')} got {result.cross_pattern}"

    return EvalCaseResult(
        case_id=case["id"],
        task=case["task"],
        passed=passed,
        message=message,
        details={
            "top_root_cause": result.top_root_cause,
            "cross_pattern": result.cross_pattern,
            "summary": result.summary,
            "root_causes": [item.root_cause_id for item in result.root_causes[:3]],
        },
    )


def evaluate_cross_correlation_case(case: Dict[str, Any], agent: CrossCorrelationAgent) -> EvalCaseResult:
    payload = case["input"]
    expected = case["expected"]
    result = agent.analyze(payload["metrics"])

    top_hit = result.hits[0] if result.hits else None
    passed = bool(top_hit) and top_hit.pattern_id == expected.get("pattern_id") and top_hit.root_cause == expected.get(
        "root_cause"
    )
    message = "ok"
    if not top_hit:
        message = "no cross-correlation hit"
    elif top_hit.pattern_id != expected.get("pattern_id"):
        message = f"pattern_id expected {expected.get('pattern_id')} got {top_hit.pattern_id}"
    elif top_hit.root_cause != expected.get("root_cause"):
        message = f"root_cause expected {expected.get('root_cause')} got {top_hit.root_cause}"

    return EvalCaseResult(
        case_id=case["id"],
        task=case["task"],
        passed=passed,
        message=message,
        details={
            "top_pattern_id": result.top_pattern_id,
            "top_root_cause": result.top_root_cause,
            "summary": result.summary,
        },
    )


def evaluate_deadlock_case(
    case: Dict[str, Any],
    agent: DeadlockAgent,
    golden_set_path: str | Path,
) -> EvalCaseResult:
    payload = case["input"]
    expected = case["expected"]
    fixture_name = payload.get("innodb_status_file", "")
    fixture_path = Path(golden_set_path).parent / fixture_name
    result = agent.analyze_file(fixture_path)

    passed = bool(result) and result.deadlock_type == expected.get("type") and result.victim == expected.get("victim")
    message = "ok"
    if not result:
        message = "failed to parse deadlock"
    elif result.deadlock_type != expected.get("type"):
        message = f"type expected {expected.get('type')} got {result.deadlock_type}"
    elif result.victim != expected.get("victim"):
        message = f"victim expected {expected.get('victim')} got {result.victim}"

    return EvalCaseResult(
        case_id=case["id"],
        task=case["task"],
        passed=passed,
        message=message,
        details={
            "type": result.deadlock_type if result else None,
            "victim": result.victim if result else None,
            "summary": result.summary if result else "",
        },
    )


def evaluate_replication_case(case: Dict[str, Any], agent: ReplicationAgent) -> EvalCaseResult:
    payload = case["input"]
    expected = case["expected"]
    result = agent.diagnose(payload["slave_status"])

    expected_rule = expected.get("rule_id")
    matched = next((finding for finding in result.findings if finding.rule_id == expected_rule), None)
    passed = matched is not None
    message = "ok"
    if not matched:
        message = f"missing rule: {expected_rule}"
    elif expected.get("level") and matched.level != expected.get("level"):
        passed = False
        message = f"level expected {expected.get('level')} got {matched.level}"

    return EvalCaseResult(
        case_id=case["id"],
        task=case["task"],
        passed=passed,
        message=message,
        details={
            "found_rule_ids": [finding.rule_id for finding in result.findings],
            "expected_rule_id": expected_rule,
            "summary": result.summary,
        },
    )


def evaluate_rag_case(case: Dict[str, Any], agent: Any) -> EvalCaseResult:
    payload = case["input"]
    expected = case["expected"]
    result = agent.query(payload["query"])

    min_recall_docs = expected.get("min_recall_docs", 1)
    source_text = " ".join(
        f"{source.get('title', '')} {source.get('file', '')} {source.get('snippet', '')}"
        for source in result.sources
    ).lower()

    passed = len(result.sources) >= min_recall_docs
    message = "ok"
    if not passed:
        message = f"retrieved {len(result.sources)} docs < {min_recall_docs}"

    for token in expected.get("source_contains", []):
        if token.lower() not in source_text:
            passed = False
            message = f"missing expected token in sources: {token}"
            break

    return EvalCaseResult(
        case_id=case["id"],
        task=case["task"],
        passed=passed,
        message=message,
        details={"source_count": len(result.sources), "confidence": result.confidence},
    )


def evaluate_nl2sql_case(case: Dict[str, Any], agent: Any) -> EvalCaseResult:
    payload = case["input"]
    expected = case["expected"]
    result = agent.generate(payload["question"])
    sql_lower = result.sql.lower()

    passed = result.status == expected.get("status", "success")
    message = "ok"
    if result.status != expected.get("status", "success"):
        message = f"status expected {expected.get('status')} got {result.status}"

    for token in expected.get("sql_contains", []):
        if token.lower() not in sql_lower:
            passed = False
            message = f"sql missing token: {token}"
            break

    return EvalCaseResult(
        case_id=case["id"],
        task=case["task"],
        passed=passed,
        message=message,
        details={"sql": result.sql, "status": result.status, "summary": result.summary},
    )


def evaluate_report_case(case: Dict[str, Any], generator: Any) -> EvalCaseResult:
    payload = case["input"]
    expected = case["expected"]
    diagnosis = payload["diagnosis"]
    report = generator.generate(diagnosis, payload["instance_id"])
    markdown = generator.render_markdown(report).lower()

    passed = True
    message = "ok"
    for token in expected.get("markdown_contains", []):
        if token.lower() not in markdown:
            passed = False
            message = f"markdown missing token: {token}"
            break

    return EvalCaseResult(
        case_id=case["id"],
        task=case["task"],
        passed=passed,
        message=message,
        details={"instance_id": report.instance_id, "severity": report.severity},
    )


def evaluate_metrics_scan_case(case: Dict[str, Any], golden_set_path: str | Path) -> EvalCaseResult:
    from ..metrics import AnomalyDetector, MetricsAnalysisAgent, PrometheusCollector

    payload = case["input"]
    expected = case["expected"]
    fixture_path = Path(golden_set_path).parent / payload["fixture_file"]
    fixture_data = json.loads(fixture_path.read_text(encoding="utf-8"))
    collector = PrometheusCollector(fixture_data=fixture_data)
    agent = MetricsAnalysisAgent(collector, AnomalyDetector(MetricsAnalysisAgent.THRESHOLDS))
    result = agent.run(payload.get("duration_minutes", 60))
    anomalies = result.get("anomalies", [])

    passed = len(anomalies) >= expected.get("min_anomalies", 1)
    message = "ok"
    if not passed:
        message = f"anomalies {len(anomalies)} < min {expected.get('min_anomalies', 1)}"

    metric_needle = expected.get("metric_contains")
    if metric_needle and not any(item.get("metric") == metric_needle for item in anomalies):
        passed = False
        message = f"missing anomaly metric: {metric_needle}"

    critical_min = expected.get("severity_critical_min")
    if critical_min is not None:
        critical_count = sum(1 for item in anomalies if item.get("severity") == "CRITICAL")
        if critical_count < critical_min:
            passed = False
            message = f"critical anomalies {critical_count} < {critical_min}"

    return EvalCaseResult(
        case_id=case["id"],
        task=case["task"],
        passed=passed,
        message=message,
        details={"anomaly_count": len(anomalies), "summary": result.get("summary", {})},
    )


def evaluate_orchestrator_case(case: Dict[str, Any], golden_set_path: str | Path) -> EvalCaseResult:
    from ..metrics import AnomalyDetector, MetricsAnalysisAgent, PrometheusCollector
    from ..orchestrator import AgentBundle, ReActOrchestrator
    from ..reporting import ReportGenerator

    payload = case["input"]
    expected = case["expected"]
    context = dict(payload.get("context", {}))

    metrics_agent = None
    fixture_key = context.pop("metrics_fixture_file", None)
    if fixture_key:
        fixture_path = Path(golden_set_path).parent / fixture_key
        fixture_data = json.loads(fixture_path.read_text(encoding="utf-8"))
        collector = PrometheusCollector(fixture_data=fixture_data)
        metrics_agent = MetricsAnalysisAgent(collector, AnomalyDetector(MetricsAnalysisAgent.THRESHOLDS))

    if context.get("innodb_status_file"):
        fixture_path = Path(golden_set_path).parent / context["innodb_status_file"]
        context["innodb_status_file"] = str(fixture_path)

    bundle = AgentBundle.create_default(metrics_agent=metrics_agent)
    bundle.report = ReportGenerator()
    orchestrator = ReActOrchestrator(bundle)
    result = orchestrator.run(payload["query"], context=context)
    tools = [step.tool for step in result.steps]

    passed = all(tool in tools for tool in expected.get("tools_contains", []))
    message = "ok"
    if not passed:
        missing = [tool for tool in expected.get("tools_contains", []) if tool not in tools]
        message = f"missing tools: {', '.join(missing)}"

    return EvalCaseResult(
        case_id=case["id"],
        task=case["task"],
        passed=passed,
        message=message,
        details={"tools": tools, "answer": result.answer[:200]},
    )


def evaluate_case(
    case: Dict[str, Any],
    handlers: Dict[str, Callable[..., EvalCaseResult]],
) -> EvalCaseResult:
    handler = handlers.get(case["task"])
    if handler is None:
        return EvalCaseResult(
            case_id=case["id"],
            task=case["task"],
            passed=False,
            message=f"unsupported task: {case['task']}",
        )
    return handler(case)


def run_evaluation(
    golden_set_path: str | Path,
    index_path: Optional[str] = None,
    tasks: Optional[List[str]] = None,
    exclude_tasks: Optional[List[str]] = None,
) -> Dict[str, Any]:
    cases = load_golden_set(golden_set_path)
    if tasks:
        cases = [case for case in cases if case["task"] in tasks]
    if exclude_tasks:
        excluded = set(exclude_tasks)
        cases = [case for case in cases if case["task"] not in excluded]

    explain_agent = ExplainDiagnosisAgent()
    index_agent = IndexAdvisorAgent()
    rewrite_agent = SQLRewriterAgent()
    root_cause_agent = RootCauseAgent()
    cross_correlation_agent = CrossCorrelationAgent()
    deadlock_agent = DeadlockAgent()
    replication_agent = ReplicationAgent()
    from ..agents.nl2sql_agent import NL2SQLAgent
    from ..reporting import ReportGenerator

    nl2sql_agent = NL2SQLAgent(schema_path=str(SCHEMA_PATH) if SCHEMA_PATH.exists() else None)
    report_generator = ReportGenerator()

    handlers: Dict[str, Callable[..., EvalCaseResult]] = {
        "explain_diagnosis": lambda case: evaluate_explain_case(case, explain_agent),
        "index_advice": lambda case: evaluate_index_case(case, index_agent),
        "sql_rewrite": lambda case: evaluate_rewrite_case(case, rewrite_agent),
        "root_cause": lambda case: evaluate_root_cause_case(case, root_cause_agent),
        "cross_correlation": lambda case: evaluate_cross_correlation_case(case, cross_correlation_agent),
        "deadlock_parse": lambda case: evaluate_deadlock_case(case, deadlock_agent, golden_set_path),
        "replication": lambda case: evaluate_replication_case(case, replication_agent),
        "nl2sql": lambda case: evaluate_nl2sql_case(case, nl2sql_agent),
        "report_generation": lambda case: evaluate_report_case(case, report_generator),
        "metrics_scan": lambda case: evaluate_metrics_scan_case(case, golden_set_path),
        "orchestrator_e2e": lambda case: evaluate_orchestrator_case(case, golden_set_path),
    }

    if index_path:
        from ..agents.rag_agent import MySQLRAGAgent

        rag_agent = MySQLRAGAgent(index_path, quiet=True)
        handlers["rag_retrieval"] = lambda case: evaluate_rag_case(case, rag_agent)

    results = [evaluate_case(case, handlers) for case in cases]
    passed = sum(1 for result in results if result.passed)
    total = len(results)

    return {
        "golden_set": str(golden_set_path),
        "total": total,
        "passed": passed,
        "pass_rate": round(passed / total, 4) if total else 0.0,
        "results": [
            {
                "id": result.case_id,
                "task": result.task,
                "passed": result.passed,
                "message": result.message,
                "details": result.details,
            }
            for result in results
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run MySQL Agent golden set evaluation")
    parser.add_argument("--golden-set", required=True, help="Path to golden_set.jsonl")
    parser.add_argument("--index-path", help="Vector index path for RAG cases")
    parser.add_argument("--tasks", nargs="*", help="Only run selected task types")
    parser.add_argument("--report", help="Write JSON report to this path")
    args = parser.parse_args()

    report = run_evaluation(args.golden_set, index_path=args.index_path, tasks=args.tasks)
    print(json.dumps(report, ensure_ascii=False, indent=2))

    if args.report:
        Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
