FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Placeholders scoped to this step only (not persisted to the running container) so
# `download-files` can import the app; real secrets are injected at runtime.
RUN SUPABASE_URL=https://placeholder.supabase.co SUPABASE_SERVICE_ROLE_KEY=placeholder \
    python main.py download-files

CMD ["python", "main.py", "start"]
