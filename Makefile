SHELL := /bin/bash
PY ?= python3
# Recipes use paths relative to this Makefile so the bundle can be moved or
# lifted into its own repository without editing targets.
#
# This project lives in its own checkout; a customer engagement lives in its
# own. Set OB_PROJECT to the artifact/project repository and every FILE, DOCX, and
# WIKI path is read relative to it, so the daily commands stay short:
#
#   export OB_PROJECT=/path/to/project-repo
#   make render FILE=docs/observability/analysis-<app>-<date>.md
#
# An absolute path always wins, and with OB_PROJECT unset nothing changes.
# ENGAGEMENT remains a compatibility alias for existing automation.
OB_PROJECT ?= $(ENGAGEMENT)
at = $(if $(OB_PROJECT),$(if $(filter /% ~%,$(1)),$(1),$(OB_PROJECT)/$(1)),$(1))

.DEFAULT_GOAL := help

.PHONY: help
help: ## Show available targets
	@grep -hE '^[a-zA-Z0-9_.-]+:.*?## ' $(MAKEFILE_LIST) \
	  | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-24s\033[0m %s\n", $$1, $$2}'

# make install HOSTS="--cursor --claude"   (default: every supported host)
.PHONY: install
install: ## Install skills and commands into an agent host (see ./install.sh --help)
	./install.sh $${HOSTS:---all}

.PHONY: test
test: ## Run contract tests over the agentry and the renderer round-trip
	$(PY) -m pytest tests skills -q

.PHONY: check
check: check-obconfig-schema check-plugin-skills check-manifest-versions ## Verify packaging is consistent

.PHONY: sync-plugin-skills
sync-plugin-skills: ## Refresh plugin skill copies and host links from canonical skills
	$(PY) scripts/sync_plugin_skills.py

.PHONY: check-plugin-skills
check-plugin-skills: ## Fail if plugin copies drifted from canonical skills
	$(PY) scripts/sync_plugin_skills.py --check

.PHONY: check-obconfig-schema
check-obconfig-schema: ## Fail if generated obconfig schema drifted from the YAML contract
	$(PY) skills/engagement-intake/scripts/generate_obconfig_schema.py --check

.PHONY: check-manifest-versions
check-manifest-versions: ## Fail if the Claude and Codex plugin versions disagree
	@$(PY) -c "import json,sys; \
	c=json.load(open('plugins/obengineer/.claude-plugin/plugin.json')); \
	x=json.load(open('plugins/obengineer/.codex-plugin/plugin.json')); \
	sys.exit(0) if c['version']==x['version'] else sys.exit(f\"version mismatch: claude {c['version']} != codex {x['version']}\")" \
	&& echo "plugin manifest versions agree"

# make render FILE=docs/observability/analysis-<app>-<date>.md [OUT=...]
.PHONY: render
render: ## Render a Markdown deliverable to .docx and verify the result
	@test -n "$(FILE)" || { echo "usage: make render FILE=<path.md> [OUT=<path.docx>] [OB_PROJECT=<repo>]"; exit 2; }
	@src="$(call at,$(FILE))"; out="$(call at,$(OUT))"; [[ -n "$$out" ]] || out="$${src%.md}.docx"; \
	  $(PY) skills/customer-doc-render/scripts/render_customer_doc.py "$$src" -o "$$out" && \
	  $(PY) skills/customer-doc-render/scripts/verify_render.py "$$src" "$$out"

# make verify-wiki WIKI="wiki/apps/<app>/versions/V<N>" OB_PROJECT=<repo>
.PHONY: verify-wiki
verify-wiki: ## Verify an agent wiki: links, frontmatter, counts, pointers, secrets
	@test -n "$(WIKI)" || { echo "usage: make verify-wiki WIKI=<wiki/apps/<app>/versions/V<N>> [OB_PROJECT=<repo>] [REPO_ROOT=<repo>]"; exit 2; }
	@root="$(REPO_ROOT)"; [[ -n "$$root" ]] || root="$(OB_PROJECT)"; \
	  $(PY) skills/instrumentation-wiki/scripts/verify_wiki.py "$(call at,$(WIKI))" \
	    $${root:+--repo-root "$$root"}

.PHONY: validate-analysis
validate-analysis: ## Validate canonical analysis JSON and optional audited worker intervals
	@test -n "$(CONTRACT)" || { echo "usage: make validate-analysis CONTRACT=<analysis-contract.json> [MANIFEST=<job-manifest.json> RESULTS=<worker-results-dir> TIMING=<run-timing.json>] [OB_PROJECT=<repo>]"; exit 2; }
	@contract="$(call at,$(CONTRACT))"; manifest="$(if $(MANIFEST),$(call at,$(MANIFEST)))"; results="$(if $(RESULTS),$(call at,$(RESULTS)))"; timing="$(if $(TIMING),$(call at,$(TIMING)))"; \
	  $(PY) skills/instrumentation-analyze/scripts/validate_analysis.py \
	    --contract "$$contract" $${manifest:+--manifest "$$manifest"} $${results:+--results "$$results"} $${timing:+--timing "$$timing"}

.PHONY: render-analysis
render-analysis: ## Deterministically render canonical analysis JSON as linked Markdown
	@test -n "$(CONTRACT)" -a -n "$(VERSION)" || { echo "usage: make render-analysis CONTRACT=<analysis-contract.json> VERSION=docs/observability/analysis/<app>/V<N> [OB_PROJECT=<repo>]"; exit 2; }
	$(PY) skills/instrumentation-analyze/scripts/render_analysis_site.py \
	  "$(call at,$(CONTRACT))" "$(call at,$(VERSION))" --clean

.PHONY: verify-analysis
verify-analysis: ## Verify linked analysis semantics, links, breadcrumbs, and optional canonical JSON
	@test -n "$(VERSION)" || { echo "usage: make verify-analysis VERSION=docs/observability/analysis/<app>/V<N> [CONTRACT=<analysis-contract.json>] [OB_PROJECT=<repo>]"; exit 2; }
	@root="$(OB_PROJECT)"; [[ -n "$$root" ]] || root="."; \
	  contract="$(if $(CONTRACT),$(call at,$(CONTRACT)))"; \
	  $(PY) skills/instrumentation-analyze/scripts/verify_analysis_site.py \
	    "$(call at,$(VERSION))" --repo-root "$$root" $${contract:+--contract "$$contract"}

.PHONY: qa-analysis
qa-analysis: ## Run representative orchestration, semantic, deterministic render, and budget QA
	$(PY) skills/instrumentation-analyze/scripts/qa_analysis.py

.PHONY: verify
verify: ## Verify an existing .docx against its Markdown source
	@test -n "$(FILE)" -a -n "$(DOCX)" || { echo "usage: make verify FILE=<path.md> DOCX=<path.docx>"; exit 2; }
	$(PY) skills/customer-doc-render/scripts/verify_render.py "$(call at,$(FILE))" "$(call at,$(DOCX))"

.PHONY: verify-ledger
verify-ledger: ## Validate an engagement provenance ledger
	@file="$(call at,$(or $(FILE),docs/observability/provenance-ledger.json))"; \
	  $(PY) skills/instrumentation-wiki/scripts/verify_provenance_ledger.py "$$file"

.PHONY: verify-results
verify-results: ## Validate read-only verification results against the accepted plan
	@test -n "$(RESULTS)" || { echo "usage: make verify-results RESULTS=<results.json> [PLAN=<verification-plan.json>] [LEDGER=<provenance-ledger.json>] [EXCLUSIONS=<exclusions.json>] [OB_PROJECT=<repo>]"; exit 2; }
	@plan="$(call at,$(or $(PLAN),docs/observability/verification-plan.json))"; \
	  results="$(call at,$(RESULTS))"; \
	  ledger="$(call at,$(or $(LEDGER),docs/observability/provenance-ledger.json))"; \
	  acceptance="$(call at,$(ACCEPTANCE))"; base="$(OB_PROJECT)"; \
	  [[ -n "$$base" ]] || base="."; \
	  exclusions=""; [[ -z "$(EXCLUSIONS)" ]] || exclusions="$(call at,$(EXCLUSIONS))"; \
	  $(PY) skills/instrumentation-verify/scripts/verify_results.py "$$plan" "$$results" \
	    --ledger "$$ledger" --repo "$$base" \
	    $${acceptance:+--acceptance "$$acceptance"} \
	    $${exclusions:+--exclusions "$$exclusions"}

# make preview DOCX=docs/observability/Guide.docx [PAGES=4] [START=92]
.PHONY: preview
preview: ## Rasterise pages of a .docx to check the layout by eye
	@test -n "$(DOCX)" || { echo "usage: make preview DOCX=<path.docx> [PAGES=4]"; exit 2; }
	@command -v soffice >/dev/null || { echo "soffice not installed; see SKILL.md"; exit 2; }
	@out=$${PREVIEW:-/tmp/doc-preview}; rm -rf "$$out"; mkdir -p "$$out"; \
	  soffice --headless --convert-to pdf --outdir "$$out" "$(call at,$(DOCX))" >/dev/null 2>&1; \
	  $(PY) skills/customer-doc-render/scripts/preview_pages.py \
	    "$$out"/*.pdf --pages $${PAGES:-4} --start $${START:-1} \
	    -o "$$out/contact-sheet.png"

.PHONY: deps
deps: ## Install renderer and test dependencies
	$(PY) -m pip install python-docx markdown-it-py==4.2.0 PyYAML==6.0.3 pytest
