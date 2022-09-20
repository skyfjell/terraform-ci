FROM ghcr.io/skyfjell/terraform-ci:tf-ci-0.0.2

WORKDIR /app
COPY main.sh /app/main.sh
COPY main.py /app/main.py
ENTRYPOINT [ "bash", "/app/main.sh"]