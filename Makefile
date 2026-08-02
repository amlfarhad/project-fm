.PHONY: setup dev verify trial demo-artifact backend-test frontend-build
SAMPLE_EVERY_MS ?= 1000
PROJECT_FM_PIPELINE_COMMIT ?= $(shell git rev-parse HEAD)
MIN_STATES ?= 2
MIN_OBSERVED_PLAYERS ?= 6
MIN_CALIBRATION_CONFIDENCE ?= 0.6
MIN_PROCESSING_FPS ?= 1.0
MIN_IDENTITY_COVERAGE ?= 0.0
MIN_OBSERVED_IDENTITY_COVERAGE ?= 0.0

setup:
	./scripts/setup-local.sh

dev:
	./scripts/start-local.sh

verify:
	./scripts/verify-local.sh

trial:
	@test -n "$(VIDEO)" || (echo "Usage: make trial VIDEO=/absolute/path/to/match.mp4" && exit 2)
	./scripts/trial-file.sh "$(VIDEO)" "$(DURATION_MS)" "$(SAMPLE_EVERY_MS)" "$(MIN_STATES)" "$(MIN_OBSERVED_PLAYERS)" "$(MIN_CALIBRATION_CONFIDENCE)" "$(MIN_PROCESSING_FPS)" "$(MIN_IDENTITY_COVERAGE)" "$(MIN_OBSERVED_IDENTITY_COVERAGE)"

demo-artifact:
	PROJECT_FM_PIPELINE_COMMIT="$(PROJECT_FM_PIPELINE_COMMIT)" backend/.venv/bin/python scripts/generate-demo-artifact.py

backend-test:
	cd backend && .venv/bin/pytest -v

frontend-build:
	cd frontend && npm run build
