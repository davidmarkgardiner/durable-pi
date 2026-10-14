FROM node:24.15.0-bookworm-slim AS node
FROM durable-agent-showcase:20261014-3
USER root
RUN apt-get update && apt-get install -y --no-install-recommends git libatomic1 libstdc++6 && rm -rf /var/lib/apt/lists/*
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY demo/ /demo/
COPY bridge.py wire.py chat.py gitops.py /bridge/
ENV PYTHONPATH=/app/generated:/app:/bridge
USER 65532:65532
CMD ["python","/bridge/bridge.py"]
