FROM python:3.12-slim

WORKDIR /app
COPY . .
RUN pip install --no-cache-dir . \
    && python -m compileall -q agent_retry_safety_bench tests \
    && python -m agent_retry_safety_bench.config config/demo.json \
    && python -m agent_retry_safety_bench.scenarios

CMD ["python", "-m", "unittest", "discover", "-s", "tests", "-v"]
