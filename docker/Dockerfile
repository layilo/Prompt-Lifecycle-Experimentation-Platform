FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml README.md requirements.txt ./
COPY src ./src
COPY configs ./configs
COPY data ./data
COPY tests ./tests
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -e .[dev]

ENV PROMPT_PLATFORM_PROFILE=local-demo
CMD ["python", "-m", "prompt_platform.cli", "demo", "run", "--profile", "local-demo", "--output-dir", "artifacts/generated/docker-demo"]

