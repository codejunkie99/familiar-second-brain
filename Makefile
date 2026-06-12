.PHONY: test smoke install-dry-run

PYTHON ?= /usr/bin/python3
VAULT ?= $(HOME)/Documents/kimi/workspace/familiar-vault

test:
	$(PYTHON) tests/test_familiar_mcp_server.py
	$(PYTHON) kimi_skill/tests/test_brain_brief.py
	$(PYTHON) kimi_skill/tests/test_inbox_triage.py
	$(PYTHON) kimi_skill/tests/test_save_to_familiar.py
	$(PYTHON) kimi_skill/tests/test_summarize_sessions.py

smoke:
	$(PYTHON) scripts/smoke_mcp.py --vault "$(VAULT)"

install-dry-run:
	$(PYTHON) scripts/install.py --dry-run --vault "$(VAULT)"
