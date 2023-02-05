FROM ghcr.io/skyfjell/terraform-ci:tf-ci-0.0.5

ENTRYPOINT [ "bash", "/app/main.sh"]