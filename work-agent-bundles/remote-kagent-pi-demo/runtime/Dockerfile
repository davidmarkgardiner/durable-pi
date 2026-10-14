ARG PYTHON_BASE=python:3.12.12-slim-bookworm
FROM ${PYTHON_BASE}
WORKDIR /app
COPY requirements.lock .
RUN pip install --no-cache-dir -r requirements.lock
COPY proto/ proto/
RUN mkdir generated && python -m grpc_tools.protoc -Iproto --python_out=generated $(find proto -name '*.proto' ! -name '._*')
COPY *.py /app/
ENV PYTHONPATH=/app/generated:/app
USER 65532:65532
EXPOSE 8080
CMD ["python", "/app/work_bridge.py"]
