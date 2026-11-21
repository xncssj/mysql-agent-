"""Replication diagnosis models."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class SlaveStatus:
    slave_io_running: str = "Yes"
    slave_sql_running: str = "Yes"
    seconds_behind_master: Optional[int] = None
    last_io_error: str = ""
    last_sql_error: str = ""
    relay_log_space: int = 0
    exec_master_log_pos: int = 0
    read_master_log_pos: int = 0
    gtid_executed: str = ""
    retrieved_gtid_set: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, object]) -> "SlaveStatus":
        return cls(
            slave_io_running=str(data.get("Slave_IO_Running", data.get("slave_io_running", "Yes"))),
            slave_sql_running=str(data.get("Slave_SQL_Running", data.get("slave_sql_running", "Yes"))),
            seconds_behind_master=_to_int(data.get("Seconds_Behind_Master", data.get("seconds_behind_master"))),
            last_io_error=str(data.get("Last_IO_Error", data.get("last_io_error", ""))),
            last_sql_error=str(data.get("Last_SQL_Error", data.get("last_sql_error", ""))),
            relay_log_space=_to_int(data.get("Relay_Log_Space", data.get("relay_log_space"))) or 0,
            exec_master_log_pos=_to_int(data.get("Exec_Master_Log_Pos", data.get("exec_master_log_pos"))) or 0,
            read_master_log_pos=_to_int(data.get("Read_Master_Log_Pos", data.get("read_master_log_pos"))) or 0,
            gtid_executed=str(data.get("Executed_Gtid_Set", data.get("gtid_executed", ""))),
            retrieved_gtid_set=str(data.get("Retrieved_Gtid_Set", data.get("retrieved_gtid_set", ""))),
        )


def _to_int(value: object) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@dataclass
class ReplicationFinding:
    rule_id: str
    rule_name: str
    level: str
    message: str
    action: str
    evidence: Dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        return {
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "level": self.level,
            "message": self.message,
            "action": self.action,
            "evidence": self.evidence,
        }


@dataclass
class ReplicationResult:
    findings: List[ReplicationFinding]
    primary_rule_id: str
    summary: str

    def to_dict(self) -> Dict[str, object]:
        return {
            "findings": [finding.to_dict() for finding in self.findings],
            "primary_rule_id": self.primary_rule_id,
            "summary": self.summary,
        }
