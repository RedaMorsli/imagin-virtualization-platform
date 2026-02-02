# syntax=docker/dockerfile:1

# Build argument to select Python base image variant (optional)
ARG PYTHON_VERSION=3.10-slim
FROM python:${PYTHON_VERSION} AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Copy application code
COPY samples/flower .


# Install runtime dependencies
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt


# Choose role at build- or run-time: server | client
ARG APP_ROLE=server
ENV APP_ROLE=${APP_ROLE}

# Run the selected role
ENTRYPOINT ["sh", "-c", "python -m ${APP_ROLE}"]
