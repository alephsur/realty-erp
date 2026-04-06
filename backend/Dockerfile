FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set work directory
WORKDIR /app

# Install system dependencies (e.g., for psycopg2)
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY pyproject.toml pyproject.toml
RUN pip install --upgrade pip uv

# Resolve and install dependencies via uv
# Since we map the volume over /app, we install to system to avoid .venv being shadowed
# Or simply create a requirements.txt on the fly:
RUN uv pip compile pyproject.toml -o requirements.txt && \
    uv pip install --system -r requirements.txt

# We don't COPY the rest of the application here because we intend to mount it 
# as a volume in docker-compose for hot-reloading development.

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
