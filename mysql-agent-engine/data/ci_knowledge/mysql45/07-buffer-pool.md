# innodb_buffer_pool_size 推荐设置

InnoDB Buffer Pool 是最重要的内存配置。生产环境通常将 `innodb_buffer_pool_size` 设为物理内存的 50%~70%。
监控 `Innodb_buffer_pool_read_requests` 与 `Innodb_buffer_pool_reads` 计算 hit rate。
命中率长期低于 95% 时，优先排查全表扫描与 Buffer Pool 不足。
