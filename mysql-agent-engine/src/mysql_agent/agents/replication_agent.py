"""Replication diagnosis agent."""
from __future__ import annotations

from typing import Dict, Optional, Union

from ..replication import ReplicationResult, ReplicationRuleEngine, SlaveStatus


class ReplicationAgent:
    """Diagnose MySQL replication issues from slave status."""

    def __init__(self):
        self.engine = ReplicationRuleEngine()

    def diagnose(
        self,
        slave_status: Union[SlaveStatus, Dict[str, object]],
        master_gtid: str = "",
    ) -> ReplicationResult:
        slave = slave_status if isinstance(slave_status, SlaveStatus) else SlaveStatus.from_dict(slave_status)
        return self.engine.analyze(slave, master_gtid=master_gtid)
