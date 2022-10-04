FROM ghcr.io/skyfjell/terraform-ci:tf-ci-0.0.3

WORKDIR /app
COPY . .
ENTRYPOINT [ "python", "-m", "action"]