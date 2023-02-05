FROM ghcr.io/skyfjell/terraform-ci:tf-ci-0.0.6

ENTRYPOINT [ "bash", "/app/main.sh"]