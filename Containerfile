FROM python:3.12-slim

WORKDIR /app
COPY . .
RUN pip install --no-cache-dir . \
    && python -m compileall -q failurebench tests \
    && python -m failurebench.config config/demo.json

CMD ["python", "-m", "unittest", "discover", "-s", "tests", "-v"]
