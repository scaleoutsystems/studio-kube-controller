FROM python:3.8.10-minimal
COPY . /app
WORKDIR /app
RUN pip install -r requirements.txt
ENTRYPOINT python event_listener.py

