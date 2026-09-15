# Reproduce the ACCESS non-R1 usage analysis end to end.
#   make all        fetch everything and rebuild (needs XDMOD_API_TOKEN)
#   make rebuild    re-run classification, analysis and page from the committed raw snapshot (no network)
#   make verify     rebuild and diff the headline numbers against the committed summary
PY ?= python3
P  = pipeline

all: fetch classify cohorts analyze site

fetch:
	$(PY) $(P)/fetch_reference.py
	$(PY) $(P)/fetch_xdmod.py

classify:
	$(PY) $(P)/classify.py

cohorts:
	$(PY) $(P)/fetch_xdmod_cohorts.py

analyze:
	$(PY) $(P)/analyze.py

site:
	$(PY) $(P)/build_site.py

rebuild: classify analyze site

verify:
	cp data/derived/summary.txt /tmp/summary_before.txt
	$(MAKE) rebuild
	diff /tmp/summary_before.txt data/derived/summary.txt && echo "summary unchanged"

serve:
	cd docs && $(PY) -m http.server 8000

.PHONY: all fetch classify cohorts analyze site rebuild verify serve
