# AgentCore Runtime requires linux/arm64 images serving /invocations and
# /ping on :8080; BedrockAgentCoreApp provides both.
FROM --platform=linux/arm64 python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY agent_app.py .
EXPOSE 8080
CMD ["python", "-u", "agent_app.py"]
