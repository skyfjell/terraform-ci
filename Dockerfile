FROM ghcr.io/skyfjell/terraform-ci:tf-ci-0.0.3

WORKDIR /app
COPY . .
RUN pip install .
ENTRYPOINT [ "python", "-m", "terraform_ci"]