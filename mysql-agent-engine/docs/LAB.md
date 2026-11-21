# 本地 Lab 验证指南（S09）

本机已验证可用镜像：

- `docker.m.daocloud.io/mysql:8.0`
- `docker.m.daocloud.io/prom/prometheus:v2.48.0`

## 一键启动

```bash
cd mysql-agent-engine
cp -n .env.example .env   # 或使用仓库内 demo .env

# 启动 MySQL + Prometheus
docker compose --profile lab up -d

# 宿主机启动 STATUS exporter（Prometheus 通过 host.docker.internal:9104 抓取）
python3.10 scripts/mysqld_status_exporter.py \
  --host=127.0.0.1 --user=exporter --password=exporterpass --listen=0.0.0.0:9104 &

# 连通性与只读防护验证
python3.10 scripts/verify_lab.py
```

期望输出关键字段：

- `mysql.ping=true`，`orders_count=500`，`write_blocked=true`
- `prometheus.up>=1`
- `metrics_agent.metrics_scanned>=1`

## 账号

| 用户 | 密码 | 用途 |
|------|------|------|
| root | rootpass | 初始化 |
| readonly | readonlypass | Agent 只读诊断 |
| exporter | exporterpass | metrics 导出 |
| app | apppass | 业务演示（可选） |

## Agent 对接

```bash
export MYSQL_HOST=127.0.0.1 MYSQL_USER=readonly MYSQL_PASSWORD=readonlypass
export MYSQL_DATABASE=ecommerce MYSQL_READONLY=1
export PROMETHEUS_URL=http://127.0.0.1:9090

python3.10 -m mysql_agent.cli metrics --prometheus-url "$PROMETHEUS_URL" --duration-minutes 5
```
