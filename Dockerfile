FROM python:3.7-alpine

WORKDIR /app

COPY requirements.txt .
RUN pip install -r /app/requirements.txt

COPY ./gricleaner.py .

ENTRYPOINT ["./gricleaner.py"]
