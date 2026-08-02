.PHONY: help up down reset logs ps seed admin apikey test health web cmp-build cmp-test test-all

help:
	@echo "Sentinel Privacy Platform"
	@echo ""
	@echo "  make up      Start postgres, redis, mongo and all three APIs"
	@echo "  make health  Check all three APIs respond"
	@echo "  make admin   Create the first DPO account (prompts for password)"
	@echo "  make apikey  Create an API key for a partner system"
	@echo "  make web     Install deps and run both frontends"
	@echo "  make logs    Tail all container logs"
	@echo "  make down    Stop everything (keeps data)"
	@echo "  make reset   Stop and DELETE all data, then re-seed from scratch"
	@echo "  make test    Run backend test suites"
	@echo "  make cmp-build  Build the embeddable CMP loader script"
	@echo "  make cmp-test   Drive the loader in real Chromium (needs make up)"
	@echo "  make test-all   Backends + loader"

up:
	docker compose up -d --build
	@echo ""
	@echo "PMP API   http://localhost:8001/docs"
	@echo "IDP API   http://localhost:8002/docs"
	@echo "Partner   http://localhost:8003/docs"
	@echo ""
	@echo "Next:  make admin   then   make web"

down:
	docker compose down

reset:
	docker compose down -v
	docker compose up -d --build
	@echo "Database recreated and re-seeded."

logs:
	docker compose logs -f

ps:
	docker compose ps

health:
	@for p in 8001 8002 8003; do \
	  printf "localhost:$$p  "; \
	  curl -s -o /dev/null -w "%{http_code}\n" http://localhost:$$p/api/v1/health || echo "DOWN"; \
	done

admin:
	@cd apps/idp-console/idp-backend && \
	 DATABASE_URL=postgresql://admin:password@localhost:5432/consent_db \
	 python3 ../../../infrastructure/scripts/create_admin.py $(EMAIL) --role dpo --name "$(NAME)"

apikey:
	@DATABASE_URL=postgresql://admin:password@localhost:5432/consent_db \
	 python3 infrastructure/scripts/create_api_key.py "$(NAME)" $(SYSTEM)

web:
	pnpm install
	pnpm dev

test:
	cd apps/pmp-portal/pmp-backend && python3 -m pytest tests -q
	cd apps/idp-console/idp-backend && python3 -m pytest tests -q
	cd apps/api/backend && python3 -m pytest tests -q

# ---------------------------------------------------------------- CMP loader
# The script customers embed. Built separately from the React apps: it has no
# framework and a hard size budget, and build.mjs fails rather than let it
# regress past 15 KB gzipped.
cmp-build:
	cd apps/cmp-loader && npm install && npm run build

# Drives the built bundle in real Chromium against a live collector. Needs
# postgres + redis up (make up) and playwright installed.
cmp-test:
	cd apps/cmp-loader && python3 browser_test.py

test-all: test cmp-test
