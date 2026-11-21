# ERROR 1205 Lock wait timeout

`ERROR 1205 (HY000): Lock wait timeout exceeded` 表示行锁等待超时。
检查 `information_schema.innodb_trx`、`innodb_lock_waits`，定位阻塞事务与被阻塞 SQL。
常见根因：长事务、缺索引导致锁范围扩大、热点行更新冲突。
