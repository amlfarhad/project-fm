.PHONY: setup dev verify trial demo-artifact backend-test frontend-build
SAMPLE_EVERY_MS ?= 1000
PROJECT_FM_PIPELINE_COMMIT ?= $(shell git rev-parse HEAD)

setup:
	./scripts/setup-local.sh

dev:
	./scripts/start-local.sh

verify:
	./scripts/verify-local.sh

trial:
	@test -n "$(VIDEO)" || (echo "Usage: make trial VIDEO=/absolute/path/to/match.mp4" && exit 2)
	./scripts/trial-file.sh "$(VIDEO)" "$(DURATION_MS)" "$(SAMPLE_EVERY_MS)"

demo-artifact:
	PROJECT_FM_PIPELINE_COMMIT="$(PROJECT_FM_PIPELINE_COMMIT)" backend/.venv/bin/python scripts/generate-demo-artifact.py

backend-test:
	cd backend && .venv/bin/pytest -v

frontend-build:
	cd frontend && npm run build
