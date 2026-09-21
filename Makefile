SHELL := /bin/bash
PY ?= python3
# Recipes use paths relative to this Makefile so the bundle can be moved or
# lifted into its own repository without editing targets.
#
# This project lives in its own checkout; a customer engagement lives in its
# own. Set ENGAGEMENT to the engagement repository and every FILE, DOCX, and
# WIKI path is read relative to it, so the daily commands stay short:
#
#   export ENGAGEMENT=~/ps-repo/Customers/Nu_Skin
#   make render FILE=docs/observability/analysis-equinox-storefront-2026-09-17.md
#
# An absolute path always wins, and with ENGAGEMENT unset nothing changes.
ENGAGEMENT ?=
at = $(if $(ENGAGEMENT),$(if $(filter /% ~%,$(1)),$(1),$(ENGAGEMENT)/$(1)),$(1))

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
check: check-plugin-skills check-manifest-versions ## Verify packaging is consistent

.PHONY: sync-plugin-skills
sync-plugin-skills: ## Refresh plugin skill copies and host links from canonical skills
	$(PY) scripts/sync_plugin_skills.py

.PHONY: check-plugin-skills
check-plugin-skills: ## Fail if plugin copies drifted from canonical skills
	$(PY) scripts/sync_plugin_skills.py --check

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
	@test -n "$(FILE)" || { echo "usage: make render FILE=<path.md> [OUT=<path.docx>] [ENGAGEMENT=<repo>]"; exit 2; }
	@src="$(call at,$(FILE))"; out="$(call at,$(OUT))"; [[ -n "$$out" ]] || out="$${src%.md}.docx"; \
	  $(PY) skills/customer-doc-render/scripts/render_customer_doc.py "$$src" -o "$$out" && \
	  $(PY) skills/customer-doc-render/scripts/verify_render.py "$$src" "$$out"

# make verify-wiki WIKI="wiki/<Customer>/<app>" ENGAGEMENT=<repo>
.PHONY: verify-wiki
verify-wiki: ## Verify an agent wiki: links, frontmatter, counts, pointers, secrets
	@test -n "$(WIKI)" || { echo "usage: make verify-wiki WIKI=<wiki/Customer/app> [ENGAGEMENT=<repo>] [REPO_ROOT=<repo>]"; exit 2; }
	@root="$(REPO_ROOT)"; [[ -n "$$root" ]] || root="$(ENGAGEMENT)"; \
	  $(PY) skills/instrumentation-wiki/scripts/verify_wiki.py "$(call at,$(WIKI))" \
	    $${root:+--repo-root "$$root"}

.PHONY: verify
verify: ## Verify an existing .docx against its Markdown source
	@test -n "$(FILE)" -a -n "$(DOCX)" || { echo "usage: make verify FILE=<path.md> DOCX=<path.docx>"; exit 2; }
	$(PY) skills/customer-doc-render/scripts/verify_render.py "$(call at,$(FILE))" "$(call at,$(DOCX))"

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
deps: ## Install the one runtime dependency
	$(PY) -m pip install python-docx pytest
