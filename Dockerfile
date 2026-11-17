# Markavi for Google Cloud Run (or any Docker host).
#   docker build -t markavi .
#   docker run -p 8080:8080 --env-file .env markavi
# Keys are never built into the image: they are passed in when it runs.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8080
WORKDIR /app

# Installed first and on its own, so a code change does not reinstall
# every package.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# The app does not need to be root.
RUN useradd --create-home app && chown -R app /app
USER app

EXPOSE 8080
# Cloud Run tells the app which port to listen on through PORT.
CMD ["sh", "-c", "streamlit run app.py --server.port=${PORT} --server.address=0.0.0.0 --server.headless=true --browser.gatherUsageStats=false"]
