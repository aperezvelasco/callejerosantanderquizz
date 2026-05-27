# Use the official Pixi container image
FROM ghcr.io/prefix-dev/pixi:latest

# Set working directory
WORKDIR /app

# Copy project files and the app package directory (required for setuptools editable install)
COPY pyproject.toml pixi.lock ./
COPY app ./app

# Install dependencies using Pixi (frozen mode)
RUN pixi install --frozen

# Copy the rest of the application code
COPY . .

# Expose ASGI server port
EXPOSE 8000

# Run the app inside the Pixi environment
CMD ["pixi", "run", "python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
