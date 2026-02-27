FROM python:3.11-slim

# Install system deps for Playwright
RUN apt-get update && apt-get install -y \
    wget curl gnupg ca-certificates \
    libglib2.0-0 libnss3 libnspr4 libdbus-1-3 \
    libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libdrm2 libxcb1 libxkbcommon0 libx11-6 \
    libxcomposite1 libxdamage1 libxext6 libxfixes3 \
    libxrandr2 libgbm1 libpango-1.0-0 libcairo2 \
    libasound2 libatspi2.0-0 libwayland-client0 \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

WORKDIR /app

# Copy project files
COPY pyproject.toml .
COPY src/ ./src/

# Install Python deps via uv
RUN uv pip install --system -e .

# Install Playwright browsers
RUN python -m playwright install chromium --with-deps

# Expose port
ENV PORT=8080
EXPOSE 8080

# Run the app
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080"]
