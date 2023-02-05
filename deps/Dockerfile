FROM python:3.11 as builder

RUN curl -L https://raw.githubusercontent.com/warrensbox/terraform-switcher/release/install.sh | bash
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

WORKDIR /build

COPY . .

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN --mount=source=.git,target=.git,type=bind \
    pip install --upgrade .

FROM python:3.11

RUN addgroup --system --gid 1001 ciuser
RUN adduser --system --uid 1001 ciuser

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /usr/local/bin/tfswitch /usr/bin/tfswitch
ENV PATH="/opt/venv/bin:$PATH:/home/ciuser/bin"
COPY --from=builder /build/main.sh /app/main.sh
COPY --from=builder /build/templates /app/templates

RUN chown -R ciuser:ciuser /app
RUN chmod 755 /app

USER ciuser
