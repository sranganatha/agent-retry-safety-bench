PYTHON ?= python
IMAGE ?= agent-failure-bench:test

.PHONY: check test test-container

check:
	$(PYTHON) -m compileall -q failurebench tests
	$(PYTHON) -m failurebench.config config/demo.json

test:
	$(PYTHON) -m unittest discover -s tests -v

test-container:
	podman build --tag $(IMAGE) .
	podman run --rm $(IMAGE)
