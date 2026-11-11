FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libglib2.0-0 libgl1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch torchvision \
    && pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
COPY tests ./tests
COPY migrations ./migrations
COPY alembic.ini ./alembic.ini
COPY phone ./phone
COPY data/approved_government_vehicles.csv ./data/approved_government_vehicles.csv
COPY data/snapshots/.gitkeep ./data/snapshots/.gitkeep
COPY yolo11n.pt ./yolo11n.pt

EXPOSE 8000

CMD ["sh", "-c", "python -m backend.bootstrap && exec python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000"]
