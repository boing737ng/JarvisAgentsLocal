FROM python:3.12-slim

# Install commonly needed data science packages
RUN pip install --no-cache-dir \
    numpy \
    pandas \
    requests

WORKDIR /work

# Run as unprivileged user
USER nobody
