# Build context is the REPO ROOT, not this directory: the whole point of
# this image is that it ships the released agentorch package and runs it
# unmodified, so src/ and configs/ must come from the repo as committed.
#
# agentorch is placed on PYTHONPATH rather than pip-installed, so that
# what executes is demonstrably the repository's own source tree and not
# a separately resolved distribution.
FROM --platform=linux/arm64 python:3.12-slim
WORKDIR /app
COPY anchor/agentcore/agent_released/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ /app/src/
# agentorch.config resolves configs/default.yaml as parents[2] of
# src/agentorch/config.py, i.e. /app/configs -- keep this layout.
COPY configs/ /app/configs/
COPY anchor/agentcore/agent_released/agent_app.py .
ENV PYTHONPATH=/app/src
EXPOSE 8080
CMD ["python", "-u", "agent_app.py"]
