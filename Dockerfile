FROM python:3.7-alpine

COPY ./requirements.txt ./gricleaner.py /app/
RUN python3 -m venv /app/.env
RUN /app/.env/bin/pip install --upgrade pip \
    && /app/.env/bin/pip install -r /app/requirements.txt \
    && rm /app/requirements.txt

COPY ./docker_entrypoint.sh /
RUN chmod u+x /docker_entrypoint.sh
ENTRYPOINT ["/docker_entrypoint.sh"]
