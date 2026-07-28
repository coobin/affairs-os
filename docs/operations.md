# 盘清运维手册

## 上线前检查

1. `.env` 中已更换应用密钥、数据库密码和管理员密码；
2. `DEBUG=false`；
3. `ALLOWED_HOSTS` 使用实际域名；
4. 入口已配置 HTTPS；
5. 数据库和 Redis 没有映射宿主机端口；
6. 备份目录位于独立磁盘或会被复制到异机；
7. 已使用非演示账号完成一次登录、领用和归还；
8. 已运行自动化测试。

## 健康检查

```bash
docker compose ps
curl -fsS http://127.0.0.1:8080/healthz
curl -fsS http://127.0.0.1:8080/api/v1/health/
```

正常情况下，所有容器都处于运行状态，`proxy` 与 `app` 显示 healthy。

## 日志

```bash
docker compose logs --tail=200 app
docker compose logs --tail=200 worker
docker compose logs --tail=200 proxy
```

日志中不应打印 `.env`、Token、数据库密码或附件内容。

## 备份

```bash
./scripts/backup.sh
```

可通过 `BACKUP_DIR` 指定其他目录：

```bash
BACKUP_DIR=/srv/affairs-os-backups ./scripts/backup.sh
```

备份完成后应检查两个文件均非空：

- `database.dump`
- `media.tar.gz`

## 恢复演练

恢复会覆盖目标环境数据，只应在空白演练环境或已确认的维护窗口执行。

1. 核对备份时间戳和目标环境；
2. 停止入口和业务进程；
3. 恢复数据库；
4. 恢复附件；
5. 启动服务并检查迁移；
6. 抽查资产数量、最近流转和附件。

示例命令：

```bash
docker compose stop proxy app worker beat
docker compose up -d db redis
docker compose exec -T db pg_restore \
  -U asset_manager \
  -d asset_manager \
  --clean \
  --if-exists < backups/时间戳/database.dump
docker compose run --rm -T --entrypoint sh app \
  -c "tar -xzf - -C /app" < backups/时间戳/media.tar.gz
docker compose up -d
```

数据库名称和用户必须与目标环境 `.env` 一致。演练完成后记录恢复耗时和抽查结果。

## 升级

不要直接使用浮动版本镜像。升级步骤：

1. 阅读应用和依赖变更；
2. 创建完整备份；
3. 在测试环境构建并运行测试；
4. 更新固定版本；
5. 重新构建并启动；
6. 检查数据库迁移、健康状态和关键流程；
7. 如失败，恢复上一份代码、镜像版本和升级前备份。

```bash
./scripts/backup.sh
docker compose build
docker compose up -d
docker compose exec app python manage.py test
```

## 常见问题

### 页面可以打开，但接口返回 502

检查 `app` 容器是否 healthy，并查看应用日志。常见原因是数据库密码不一致或迁移失败。

### 修改 `.env` 后没有生效

重新创建相关容器：

```bash
docker compose up -d --force-recreate app worker beat proxy
```

### 演示账号无法登录

重新执行演示数据命令。该命令可重复执行，并会采用 `.env` 中配置的管理员密码：

```bash
docker compose exec app python manage.py seed_demo
```

### 资产能否删除

不能。错误录入可在后续增加“作废”动作；已经发生业务流转的资产必须通过退役或处置结束生命周期。
