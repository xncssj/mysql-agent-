-- readonly + exporter accounts (SELECT only for app diagnostics)
CREATE USER IF NOT EXISTS 'readonly'@'%' IDENTIFIED BY 'readonlypass';
GRANT SELECT, SHOW VIEW, PROCESS, REPLICATION CLIENT ON *.* TO 'readonly'@'%';
GRANT SELECT ON ecommerce.* TO 'readonly'@'%';

CREATE USER IF NOT EXISTS 'exporter'@'%' IDENTIFIED BY 'exporterpass';
GRANT PROCESS, REPLICATION CLIENT, SELECT ON *.* TO 'exporter'@'%';

FLUSH PRIVILEGES;
