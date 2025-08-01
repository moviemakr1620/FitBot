FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y nano

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Set time zone to match host
RUN ln -sf /usr/share/zoneinfo/${TIMEZONE} /etc/localtime
RUN echo "${TIMEZONE}" > /etc/timezone

CMD ["python", "bot.py"]
