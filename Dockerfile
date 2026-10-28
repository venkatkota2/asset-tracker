FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
WORKDIR /app
COPY pyproject.toml README.md requirements.lock ./
COPY src ./src
RUN python -m pip install --no-cache-dir . -c requirements.lock
COPY web ./web
RUN useradd --uid 10001 --create-home appuser && chown -R appuser:appuser /app
USER appuser
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "indexlens.api:app", "--host", "0.0.0.0", "--port", "8000"]

