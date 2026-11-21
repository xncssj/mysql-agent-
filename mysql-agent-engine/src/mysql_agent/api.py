#!/usr/bin/env python3
"""REST API for mysql-agent-engine.

作者: 李文
日期: 2025-08-25
"""
from __future__ import annotations

import json
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from mysql_agent.agents.deadlock_agent import DeadlockAgent
from mysql_agent.agents.explain_agent import ExplainDiagnosisAgent
from mysql_agent.agents.index_agent import IndexAdvisorAgent
from mysql_agent.agents.replication_agent import ReplicationAgent
from mysql_agent.agents.root_cause_agent import RootCauseAgent
from mysql_agent.agents.sql_rewriter import SQLRewriterAgent
from mysql_agent.orchestrator import AgentBundle, MySQLOrchestrator, ReActOrchestrator
from mysql_agent.llm import HeuristicLLMClient, OpenAILLMClient


# ========== Request/Response Models ==========

class ExplainRequest(BaseModel):
    sql: str = Field(..., description="SQL 语句")
    explain: dict = Field(default_factory=lambda: {"type": "ALL", "rows": 1_000_000}, description="EXPLAIN 结果")

class IndexRequest(BaseModel):
    sql: str = Field(..., description="SQL 语句")
    table: str = Field(..., description="表名")
    explain: dict = Field(default_factory=lambda: {"type": "ALL", "rows": 1_000_000})

class RewriteRequest(BaseModel):
    sql: str = Field(..., description="SQL 语句")

class DeadlockRequest(BaseModel):
    innodb_status: str = Field(..., description="SHOW ENGINE INNODB STATUS 输出")

class ReplicationRequest(BaseModel):
    slave_status: dict = Field(default_factory=dict, description="SHOW SLAVE STATUS 结果")

class ChatRequest(BaseModel):
    query: str = Field(..., description="用户问题")
    context: dict = Field(default_factory=dict, description="上下文信息")
    llm: str = Field(default="heuristic", description="LLM 类型: heuristic / openai")

class EvalRequest(BaseModel):
    golden_set: str = Field(..., description="Golden Set JSONL 文件路径")


# ========== App Lifecycle ==========

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup/shutdown."""
    # Startup: build components once
    index_path = os.environ.get("INDEX_PATH", "data/vector_index")
    app.state.index_path = Path(index_path) if Path(index_path).exists() else None
    app.state.start_time = time.time()
    yield
    # Shutdown: cleanup if needed


app = FastAPI(
    title="MySQL Agent Engine",
    description="LLM-driven MySQL Performance Analysis Agent",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ========== Health ==========

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": "0.1.0",
        "uptime_seconds": int(time.time() - app.state.start_time),
        "components": {
            "vector_index": app.state.index_path is not None,
        }
    }


@app.get("/config")
async def get_config():
    """Show current configuration (safe fields only)."""
    return {
        "llm_base_url": os.environ.get("LLM_BASE_URL", "not set"),
        "llm_model": os.environ.get("LLM_MODEL", "not set"),
        "index_path": str(app.state.index_path) if app.state.index_path else "not set",
    }


# ========== Diagnostic Endpoints ==========

@app.post("/explain")
async def diagnose_explain(req: ExplainRequest):
    """Analyze SQL EXPLAIN output."""
    agent = ExplainDiagnosisAgent()
    result = agent.diagnose(req.sql, req.explain)
    return result.to_dict()


@app.post("/index")
async def advise_index(req: IndexRequest):
    """Get index advice for SQL."""
    agent = IndexAdvisorAgent()
    result = agent.advise(req.sql, req.table, req.explain)
    return result.to_dict()


@app.post("/rewrite")
async def rewrite_sql(req: RewriteRequest):
    """Rewrite SQL for optimization."""
    agent = SQLRewriterAgent()
    result = agent.rewrite(req.sql)
    return result.to_dict()


@app.post("/deadlock")
async def analyze_deadlock(req: DeadlockRequest):
    """Analyze deadlock from INNODB STATUS."""
    agent = DeadlockAgent()
    result = agent.analyze(req.innodb_status)
    return result.to_dict() if result else {"status": "no_deadlock"}


@app.post("/replication")
async def diagnose_replication(req: ReplicationRequest):
    """Diagnose replication issues."""
    agent = ReplicationAgent()
    result = agent.diagnose(req.slave_status)
    return result.to_dict()


@app.post("/root-cause")
async def diagnose_root_cause(anomalies: list[dict]):
    """Diagnose root cause from anomaly list."""
    agent = RootCauseAgent()
    result = agent.diagnose_from_anomalies(anomalies)
    return result.to_dict()


# ========== Orchestrator ==========

@app.post("/chat")
async def chat(req: ChatRequest):
    """ReAct orchestrator chat endpoint."""
    llm = None
    if req.llm == "openai":
        base_url = os.environ.get("LLM_BASE_URL")
        api_key = os.environ.get("LLM_API_KEY", "sk-placeholder")
        model = os.environ.get("LLM_MODEL", "gpt-4o-mini")
        llm = OpenAILLMClient(base_url=base_url, api_key=api_key, model=model)

    bundle = AgentBundle.create_default(
        index_path=str(app.state.index_path) if app.state.index_path else None,
        llm_client=llm,
    )
    orchestrator = ReActOrchestrator(bundle, llm_client=llm)
    result = orchestrator.run(req.query, context=req.context)
    return result.to_dict()


# ========== Evaluation ==========

@app.post("/eval")
async def run_eval(req: EvalRequest):
    """Run golden set evaluation."""
    from mysql_agent.eval.run import run_evaluation
    report = run_evaluation(req.golden_set, index_path=str(app.state.index_path) if app.state.index_path else None)
    return report


# ========== Entrypoint ==========

def main():
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()