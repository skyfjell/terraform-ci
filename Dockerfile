FROM python:3.10

RUN curl -L https://raw.githubusercontent.com/warrensbox/terraform-switcher/release/install.sh | bash
RUN apt-get update && apt-get install -y jq curl

WORKDIR /app
COPY main.sh /app/main.sh
COPY main.py /app/main.py

RUN python -m pip install -U pip awscli checkov pandas

ENTRYPOINT [ "bash", "/app/main.sh"]