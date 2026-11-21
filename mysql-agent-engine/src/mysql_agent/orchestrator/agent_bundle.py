"""Agent bundle for orchestrator."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ..agents.cross_correlation_agent import CrossCorrelationAgent
from ..agents.deadlock_agent import DeadlockAgent
from ..agents.explain_agent import ExplainDiagnosisAgent
from ..agents.index_agent import IndexAdvisorAgent
from ..agents.nl2sql_agent import NL2SQLAgent
from ..agents.replication_agent import ReplicationAgent
from ..agents.root_cause_agent import RootCauseAgent
from ..agents.sql_rewriter import SQLRewriterAgent
from ..metrics import AnomalyDetector, MetricsAnalysisAgent, PrometheusCollector
from ..prompts import PromptBuilder
from ..reporting import ReportGenerator

DEFAULT_SCHEMA = (
    Path(__file__).resolve().parents[2] / "data/schema/ecommerce.json"
)


@dataclass
class AgentBundle:
    explain: ExplainDiagnosisAgent
    index: IndexAdvisorAgent
    rewrite: SQLRewriterAgent
    root_cause: RootCauseAgent
    cross_correlation: CrossCorrelationAgent
    deadlock: DeadlockAgent
    replication: ReplicationAgent
    rag: Optional[object] = None
    metrics: Optional[MetricsAnalysisAgent] = None
    nl2sql: Optional[NL2SQLAgent] = None
    report: Optional[ReportGenerator] = None
    prompt_builder: Optional[PromptBuilder] = None

    @classmethod
    def create_default(
        cls,
        index_path: Optional[str] = None,
        metrics_agent: Optional[MetricsAnalysisAgent] = None,
        prometheus_url: Optional[str] = None,
        schema_path: Optional[str] = None,
        llm_client: Optional[object] = None,
    ) -> "AgentBundle":
        prompt_builder = PromptBuilder()
        rag = None
        if index_path:
            from ..agents.rag_agent import MySQLRAGAgent

            rag = MySQLRAGAgent(index_path, quiet=True, llm_client=llm_client, prompt_builder=prompt_builder)

        metrics = metrics_agent
        if metrics is None and prometheus_url:
            collector = PrometheusCollector(prometheus_url=prometheus_url)
            metrics = MetricsAnalysisAgent(collector, AnomalyDetector(MetricsAnalysisAgent.THRESHOLDS))

        schema = schema_path or (str(DEFAULT_SCHEMA) if DEFAULT_SCHEMA.exists() else None)
        nl2sql = NL2SQLAgent(schema_path=schema, llm_client=llm_client, prompt_builder=prompt_builder) if schema else None
        report = ReportGenerator(prompt_builder=prompt_builder, rag_agent=rag)

        return cls(
            explain=ExplainDiagnosisAgent(),
            index=IndexAdvisorAgent(),
            rewrite=SQLRewriterAgent(),
            root_cause=RootCauseAgent(),
            cross_correlation=CrossCorrelationAgent(),
            deadlock=DeadlockAgent(),
            replication=ReplicationAgent(),
            rag=rag,
            metrics=metrics,
            nl2sql=nl2sql,
            report=report,
            prompt_builder=prompt_builder,
        )
