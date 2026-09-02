PYTHON ?= python
IMAGE ?= agent-failure-bench:test

.PHONY: check report run test test-container

check:
	$(PYTHON) -m compileall -q failurebench tests
	$(PYTHON) -m failurebench.config config/demo.json
	$(PYTHON) -m failurebench.scenarios

test:
	$(PYTHON) -m unittest discover -s tests -v

run:
	podman build --tag $(IMAGE) .
	podman run --rm $(IMAGE) python -m failurebench.cli

report:
	podman build --tag $(IMAGE) .
	podman run --rm --volume "$(CURDIR):/workspace" $(IMAGE) python -m failurebench.benchmark /workspace/artifacts

test-container:
	podman build --tag $(IMAGE) .
	podman run --rm $(IMAGE)
