FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt && groupadd -r wz && useradd -r -g wz wz
COPY wichtelzauber/ ./wichtelzauber/
RUN mkdir -p /app/data && chown -R wz:wz /app
USER wz
ENV WZ_DATABASE=/app/data/wichtelzauber.sqlite3
EXPOSE 8000
CMD ["python","-m","uvicorn","wichtelzauber.app:app","--host","0.0.0.0","--port","8000"]
