FROM durable-agent-showcase:20261014-3
COPY application.py /checkout/application.py
ARG APP_VERSION
ENV APP_VERSION=$APP_VERSION
CMD ["python", "/checkout/application.py"]
