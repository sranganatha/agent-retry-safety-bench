PYTHON ?= python
IMAGE ?= agent-retry-safety-bench:test

.PHONY: check report run test test-container

check:
	$(PYTHON) -m compileall -q agent_retry_safety_bench tests
	$(PYTHON) -m agent_retry_safety_bench.config config/demo.json
	$(PYTHON) -m agent_retry_safety_bench.scenarios

test:
	$(PYTHON) -m unittest discover -s tests -v

run:
	podman build --tag $(IMAGE) .
	podman run --rm $(IMAGE) python -m agent_retry_safety_bench.cli

report:
	podman build --tag $(IMAGE) .
	podman run --rm --volume "$(CURDIR):/workspace" $(IMAGE) python -m agent_retry_safety_bench.benchmark /workspace/artifacts

test-container:
	podman build --tag $(IMAGE) .
	podman run --rm $(IMAGE)
