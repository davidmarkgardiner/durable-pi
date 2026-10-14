ARG PYTHON_BASE=python:3.12.12-slim-bookworm
FROM ${PYTHON_BASE}
COPY application.py /application.py
ARG APP_VERSION
ENV APP_VERSION=$APP_VERSION
USER 65532:65532
CMD ["python", "/application.py"]
