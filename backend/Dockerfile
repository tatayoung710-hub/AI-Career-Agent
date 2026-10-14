FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml requirements.lock ./
COPY app ./app
RUN pip install --no-cache-dir -r requirements.lock .
COPY alembic.ini ./
COPY alembic ./alembic
RUN mkdir -p /app/data && useradd --uid 10001 --create-home career && chown -R career:career /app
USER career
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
