FROM python:3.10

RUN curl -L https://raw.githubusercontent.com/warrensbox/terraform-switcher/release/install.sh | bash
RUN apt-get update && apt-get install -y jq curl 
RUN python -m pip install -U pip awscli==1.25.44 checkov==2.1.87 pandas==1.4.3 requests==2.28.1

