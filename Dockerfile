# CPU foundation image, not the eventual CUDA inference/training image.
# Pin image digest and resolved dependency lock at the release gate.
FROM python:3.11-slim
ARG INSTALL_EXTRAS=serve
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
COPY app ./app
RUN pip install --no-cache-dir ".[${INSTALL_EXTRAS}]" \
    && useradd --create-home --uid 10001 vidoclens
USER vidoclens
EXPOSE 8000
CMD ["uvicorn", "vidoclens.serving.api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
