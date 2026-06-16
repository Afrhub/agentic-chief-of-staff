COMPOSE = docker compose -f docker-compose.prod.yml

.PHONY: up down restart logs ps seed smoke local-up clean help

help:
	@echo "AI Chief of Staff — self-hosted stack"
	@echo "  make up         build + start (db, backend, web)"
	@echo "  make seed       create the demo founder"
	@echo "  make smoke      run the end-to-end smoke test"
	@echo "  make logs       tail backend logs"
	@echo "  make ps         show running services"
	@echo "  make local-up   start with the fully-local LLM (ollama) profile"
	@echo "  make down       stop the stack"
	@echo "  make clean      stop and DELETE the data volume"

up:
	@test -f .env || cp .env.example .env
	$(COMPOSE) up -d --build
	@echo "Up. Open http://localhost:$${WEB_PORT:-8080}  — then: make seed && make smoke"

restart:
	$(COMPOSE) up -d --build

local-up:
	@test -f .env || cp .env.example .env
	$(COMPOSE) --profile local-llm up -d --build

seed:
	$(COMPOSE) exec -T backend python seed.py

smoke:
	./smoke.sh

logs:
	$(COMPOSE) logs -f backend

ps:
	$(COMPOSE) ps

down:
	$(COMPOSE) down

clean:
	$(COMPOSE) down -v
