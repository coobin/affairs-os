# AffairsOS

AffairsOS 是一个面向企业行政团队的开源事务管理平台，以清晰、易用和可自托管为目标。

目前覆盖以下业务：

- 资产台账、自动编码、领用、借用、归还、调拨、维修、冻结、报废和完整流转记录；
- Excel 资产导入、预检、批量补齐、导出和数据质量检查；
- 易耗品库存、出入库、保障数量、采购清单和库存盘点；
- 员工自助申请、管理员分配以及按责任人展示现有借用资产；
- 车辆档案、派车、维修、保养、保险和车辆费用；
- 采购申请、采购单、供应商及合同管理；
- 统一行政费用台账，为后续预算系统集成保留数据基础；
- OIDC 单点登录、板块管理员和细粒度管理范围；
- 到期事项和待处理事务邮件通知；
- Docker Compose 部署、健康检查、持久化存储和备份。

## 技术栈

- 后端：Django、Django REST Framework、PostgreSQL、Redis、Celery
- 前端：Vue 3、TypeScript、Vite
- 部署：Docker Compose、Nginx、Gunicorn

## Docker 快速启动

要求 Docker Engine 和 Docker Compose v2。

```bash
cp .env.example .env
```

至少修改 `.env` 中的以下配置：

- `SECRET_KEY`
- `POSTGRES_PASSWORD`
- `DATABASE_URL`
- `DJANGO_SUPERUSER_PASSWORD`

然后执行：

```bash
docker compose build
docker compose up -d
```

系统默认访问地址为 <http://localhost:8080>。如需演示数据，可在仅用于测试的环境中执行：

```bash
docker compose exec app python manage.py seed_demo
```

## 身份认证

生产环境建议通过 OIDC 接入 Authelia、Keycloak、Authentik 或其他兼容身份提供方。请在 `.env` 中配置：

- `OIDC_ISSUER`
- `OIDC_CLIENT_ID`
- `OIDC_CLIENT_SECRET`
- `OIDC_REDIRECT_URI`

本地密码登录入口为 `/passwordLogin`，仅建议用于开发和应急管理账户。

## 常用操作

```bash
docker compose ps
docker compose logs -f app worker
docker compose exec app python manage.py test
./scripts/backup.sh
docker compose down
```

请勿对保存正式数据的环境执行 `docker compose down -v`。

## 本地开发

后端：

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
cd backend
../.venv/bin/python manage.py migrate
../.venv/bin/python manage.py runserver
```

前端：

```bash
cd frontend
npm ci
npm run dev
```

前端开发地址为 <http://localhost:5173>，开发服务器会把 `/api` 转发到本地 Django。

## 数据与网络安全

- `.env`、备份、附件、构建产物和本地运维信息不会纳入版本控制；
- 数据库和 Redis 仅加入 Docker 内部网络，不绑定宿主机端口；
- Docker 网络由 Docker 自动分配网段，不使用固定地址；
- 生产环境必须使用独立的强密钥和密码；
- 资产业务数据不应提交到代码仓库。

## 备份

`scripts/backup.sh` 会生成 PostgreSQL 备份、附件压缩包和当前 Compose 文件。建议把备份复制到另一台主机或对象存储，并定期验证恢复流程。

## 许可证

AffairsOS 使用 [MIT License](LICENSE) 发布。
