"""Replication rules RP01-RP10."""
from __future__ import annotations

from typing import List, Optional

from .models import ReplicationFinding, ReplicationResult, SlaveStatus


class ReplicationRuleEngine:
    """Analyze SHOW SLAVE STATUS style payloads."""

    def analyze(self, slave: SlaveStatus, master_gtid: str = "") -> ReplicationResult:
        findings: List[ReplicationFinding] = []

        if slave.slave_io_running != "Yes":
            findings.append(
                ReplicationFinding(
                    rule_id="RP01",
                    rule_name="IO 线程停止",
                    level="CRITICAL",
                    message=f"IO 线程停止: {slave.last_io_error or 'unknown error'}",
                    action="检查主库连接、网络、binlog 权限与防火墙",
                    evidence={"last_io_error": slave.last_io_error},
                )
            )

        if slave.slave_sql_running != "Yes":
            findings.append(
                ReplicationFinding(
                    rule_id="RP02",
                    rule_name="SQL 线程停止",
                    level="CRITICAL",
                    message=f"SQL 线程停止: {slave.last_sql_error or 'unknown error'}",
                    action="分析 Last_SQL_Error，决定 skip 或 rebuild",
                    evidence={"last_sql_error": slave.last_sql_error},
                )
            )

        if slave.seconds_behind_master is not None and slave.seconds_behind_master > 300:
            findings.append(
                ReplicationFinding(
                    rule_id="RP03",
                    rule_name="大延迟",
                    level="WARNING",
                    message=f"复制延迟 {slave.seconds_behind_master}s",
                    action="检查从库 CPU/IO/锁等待，考虑并行复制",
                    evidence={"seconds_behind_master": slave.seconds_behind_master},
                )
            )

        relay_lag = slave.read_master_log_pos - slave.exec_master_log_pos
        if relay_lag > 100 * 1024 * 1024:
            findings.append(
                ReplicationFinding(
                    rule_id="RP05",
                    rule_name="Relay Log 堆积",
                    level="WARNING",
                    message=f"Relay Log 堆积 {relay_lag / 1024 / 1024:.1f}MB",
                    action="SQL 线程回放速度不足，检查大事务与并行复制",
                    evidence={"relay_lag_bytes": relay_lag},
                )
            )

        if master_gtid and slave.gtid_executed and master_gtid != slave.gtid_executed:
            findings.append(
                ReplicationFinding(
                    rule_id="RP06",
                    rule_name="GTID 差异",
                    level="CRITICAL",
                    message="主从 GTID 集合不一致",
                    action="评估数据一致性并执行修复",
                    evidence={"master_gtid": master_gtid, "slave_gtid": slave.gtid_executed},
                )
            )

        if slave.seconds_behind_master is not None and slave.seconds_behind_master > 60:
            findings.append(
                ReplicationFinding(
                    rule_id="RP10",
                    rule_name="只读实例延迟读",
                    level="WARNING",
                    message="从库存在可读延迟，应用可能读到旧数据",
                    action="读主库或启用延迟感知路由",
                    evidence={"seconds_behind_master": slave.seconds_behind_master},
                )
            )

        primary_rule_id = findings[0].rule_id if findings else ""
        summary = findings[0].message if findings else "复制状态正常"
        return ReplicationResult(findings=findings, primary_rule_id=primary_rule_id, summary=summary)
