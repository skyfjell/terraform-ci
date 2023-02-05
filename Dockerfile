FROM ghcr.io/skyfjell/terraform-ci:tf-ci-0.0.4

ENTRYPOINT [ "bash", "/app/main.sh"]