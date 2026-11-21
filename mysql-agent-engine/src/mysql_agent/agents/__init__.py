"""Agent implementations.

作者: 李文
日期: 2025-08-25
"""

__all__ = [
    "ExplainDiagnosisAgent",
    "ExplainDiagnosisResult",
    "IndexAdvisorAgent",
    "IndexAdviceResult",
    "SQLRewriterAgent",
    "RootCauseAgent",
    "CrossCorrelationAgent",
    "DeadlockAgent",
    "ReplicationAgent",
    "MySQLRAGAgent",
    "RAGResult",
]


def __getattr__(name: str):
    if name in ("ExplainDiagnosisAgent", "ExplainDiagnosisResult"):
        from .explain_agent import ExplainDiagnosisAgent, ExplainDiagnosisResult

        return {
            "ExplainDiagnosisAgent": ExplainDiagnosisAgent,
            "ExplainDiagnosisResult": ExplainDiagnosisResult,
        }[name]
    if name in ("IndexAdvisorAgent", "IndexAdviceResult"):
        from .index_agent import IndexAdviceResult, IndexAdvisorAgent

        return {
            "IndexAdvisorAgent": IndexAdvisorAgent,
            "IndexAdviceResult": IndexAdviceResult,
        }[name]
    if name in ("SQLRewriterAgent",):
        from .sql_rewriter import SQLRewriterAgent

        return SQLRewriterAgent
    if name in ("RootCauseAgent",):
        from .root_cause_agent import RootCauseAgent

        return RootCauseAgent
    if name in ("CrossCorrelationAgent",):
        from .cross_correlation_agent import CrossCorrelationAgent

        return CrossCorrelationAgent
    if name in ("DeadlockAgent",):
        from .deadlock_agent import DeadlockAgent

        return DeadlockAgent
    if name in ("ReplicationAgent",):
        from .replication_agent import ReplicationAgent

        return ReplicationAgent
    if name in ("MySQLRAGAgent", "RAGResult"):
        from .rag_agent import MySQLRAGAgent, RAGResult

        return {"MySQLRAGAgent": MySQLRAGAgent, "RAGResult": RAGResult}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")