FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8083

CMD ["python", "pubg_web.py", "--host", "0.0.0.0", "--port", "8083", "--base-path", "/pubg"]
