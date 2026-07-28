.PHONY: build up down logs seed test backup

build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f app worker

seed:
	docker compose exec app python manage.py seed_demo

test:
	docker compose exec app python manage.py test

backup:
	./scripts/backup.sh
