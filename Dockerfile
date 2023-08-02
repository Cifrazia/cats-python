FROM python:3.10.9-slim-buster
ENV _CODE=/code
WORKDIR $_CODE
COPY requirements.txt $_CODE
RUN pip install -U pip && \
    pip install -r requirements.txt

COPY cats $_CODE/cats
COPY test_server $_CODE
EXPOSE 9095
CMD ["python3", "server.py"]
