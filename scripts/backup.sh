#!/bin/sh
set -eu

backup_root="${BACKUP_DIR:-./backups}"
case "$backup_root" in
  ""|"/"|".")
    echo "BACKUP_DIR 不能指向空路径、根目录或当前目录。" >&2
    exit 1
    ;;
esac

timestamp="$(date +%Y%m%d-%H%M%S)"
target="${backup_root%/}/${timestamp}"
mkdir -p "$target"

db_name="${POSTGRES_DB:-asset_manager}"
db_user="${POSTGRES_USER:-asset_manager}"

docker compose exec -T db pg_dump -U "$db_user" -d "$db_name" -Fc > "$target/database.dump"
docker compose exec -T app tar -czf - media > "$target/media.tar.gz"
cp compose.yml "$target/compose.yml"

echo "备份完成：$target"
