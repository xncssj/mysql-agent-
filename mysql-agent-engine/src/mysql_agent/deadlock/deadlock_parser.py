"""Parse SHOW ENGINE INNODB STATUS deadlock sections."""
from __future__ import annotations

import re
from typing import List, Optional

from .models import DeadlockInfo, DeadlockTransaction, LockInfo


class DeadlockParser:
    """Parse LATEST DETECTED DEADLOCK sections."""

    DEADLOCK_SECTION = re.compile(
        r"LATEST DETECTED DEADLOCK\s+(.*?)(?:\n-{8,}|\Z)",
        re.DOTALL | re.IGNORECASE,
    )
    TRX_HEADER = re.compile(r"\*\*\* \((\d)\) TRANSACTION:", re.IGNORECASE)
    HOLDS_LOCK = re.compile(
        r"\*\*\* \(\d\) HOLDS THE LOCK\(S\):\s*(.*?)(?=\*\*\*|\Z)",
        re.DOTALL | re.IGNORECASE,
    )
    WAITING_LOCK = re.compile(
        r"\*\*\* \(\d\) WAITING FOR THIS LOCK TO BE GRANTED:\s*(.*?)(?=\*\*\*|\Z)",
        re.DOTALL | re.IGNORECASE,
    )
    ROLLBACK = re.compile(r"WE ROLL BACK TRANSACTION \((\d)\)", re.IGNORECASE)

    def parse(self, innodb_status: str) -> Optional[DeadlockInfo]:
        section_match = self.DEADLOCK_SECTION.search(innodb_status)
        if not section_match:
            return None

        section = section_match.group(1).strip()
        lines = section.splitlines()
        timestamp = lines[0].strip() if lines else ""

        transactions: dict[int, DeadlockTransaction] = {}
        for match in self.TRX_HEADER.finditer(section):
            trx_num = int(match.group(1))
            start = match.end()
            next_match = self.TRX_HEADER.search(section, start)
            block = section[start : next_match.start() if next_match else len(section)]
            transactions[trx_num] = self._parse_transaction(block)

        holds_blocks = list(self.HOLDS_LOCK.finditer(section))
        waiting_blocks = list(self.WAITING_LOCK.finditer(section))
        trx_nums = sorted(transactions.keys())
        if len(trx_nums) >= 1 and len(holds_blocks) >= 1:
            transactions[trx_nums[0]].locks_held = self._parse_lock_lines(holds_blocks[0].group(1), waiting=False)
        if len(trx_nums) >= 1 and len(waiting_blocks) >= 1:
            transactions[trx_nums[0]].locks_waiting = self._parse_lock_lines(waiting_blocks[0].group(1), waiting=True)
        if len(trx_nums) >= 2 and len(holds_blocks) >= 2:
            transactions[trx_nums[1]].locks_held = self._parse_lock_lines(holds_blocks[1].group(1), waiting=False)
        if len(trx_nums) >= 2 and len(waiting_blocks) >= 2:
            transactions[trx_nums[1]].locks_waiting = self._parse_lock_lines(waiting_blocks[1].group(1), waiting=True)

        victim_match = self.ROLLBACK.search(section)
        victim = int(victim_match.group(1)) if victim_match else 2
        if 1 not in transactions or 2 not in transactions:
            return None

        return DeadlockInfo(
            timestamp=timestamp,
            transaction_1=transactions[1],
            transaction_2=transactions[2],
            victim=victim,
            raw_text=section,
        )

    def _parse_transaction(self, text: str) -> DeadlockTransaction:
        trx_id_match = re.search(r"TRANSACTION (\d+)", text)
        thread_match = re.search(r"MySQL thread id (\d+)", text)
        query_match = re.search(r"query id \d+.*?\n(.+)", text, re.IGNORECASE | re.DOTALL)
        query_text = query_match.group(1).strip() if query_match else ""
        return DeadlockTransaction(
            trx_id=trx_id_match.group(1) if trx_id_match else "",
            thread_id=int(thread_match.group(1)) if thread_match else 0,
            query_text=query_text,
        )

    def _parse_lock_lines(self, block: str, waiting: bool) -> List[LockInfo]:
        locks: List[LockInfo] = []
        for line in block.strip().splitlines():
            table_match = re.search(r"table `([^`]+)`\.`([^`]+)`", line)
            if not table_match:
                continue
            index_match = re.search(r"index (\S+)", line)
            mode_match = re.search(r"lock_mode (\S+)", line)
            locks.append(
                LockInfo(
                    lock_type="RECORD" if "RECORD" in line.upper() else "TABLE",
                    table=f"{table_match.group(1)}.{table_match.group(2)}",
                    index=index_match.group(1) if index_match else "PRIMARY",
                    mode=mode_match.group(1) if mode_match else "X",
                    waiting=waiting,
                )
            )
        return locks
