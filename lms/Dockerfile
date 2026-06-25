# ── Stage 1: Pick a base image ────────────────────────────────
# We start from an official Python image, not a blank OS
# "3.12-slim" means Python 3.12 on minimal Debian Linux (smaller size)
# This becomes the foundation of our container
FROM python:3.12-slim

# ── Stage 2: Set environment variables ────────────────────────
# PYTHONDONTWRITEBYTECODE=1 → stops Python creating .pyc files (junk in containers)
# PYTHONUNBUFFERED=1 → logs print immediately to terminal (no internal buffering)
#                      critical for seeing Gunicorn logs in real time
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# ── Stage 3: Set working directory ────────────────────────────
# This creates /app inside the container and makes it the default directory
# Every command after this runs from /app
WORKDIR /app

# ── Stage 4: Install dependencies ─────────────────────────────
# COPY requirements.txt first (before copying all your code)
# Why? Docker caches each step. If your code changes but requirements.txt
# doesn't, Docker skips reinstalling packages — much faster rebuilds
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Stage 5: Copy your project code ───────────────────────────
# Now copy everything else (your Django code)
# The . . means: copy from current folder → into /app inside container
COPY . .

# ── Stage 6: Expose the port ──────────────────────────────────
# Documents that this container listens on port 8000
# This does NOT publish the port — docker-compose handles that
EXPOSE 8000

# ── Stage 7: Start the server ─────────────────────────────────
# This runs when the container starts
# We use Gunicorn with Uvicorn workers — real production server!
CMD ["gunicorn", "lms.asgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--worker-class", "uvicorn.workers.UvicornWorker"]