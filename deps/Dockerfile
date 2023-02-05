FROM python:3.11 as builder

RUN curl -L https://raw.githubusercontent.com/warrensbox/terraform-switcher/release/install.sh | bash
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . .

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN --mount=source=.git,target=.git,type=bind \
    pip install --upgrade .

FROM python:3.11

RUN addgroup --system --gid 1001 ciuser
RUN adduser --system --uid 1001 ciuser

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /usr/local/bin/tfswitch /usr/bin/tfswitch
ENV PATH="/opt/venv/bin:$PATH:/home/ciuser/bin"
COPY main.sh /app/main.sh
ADD templates /app/templates

USER ciuser
