FROM python:3.12-slim

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libc6-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY splash/control/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir websockets

# Copy source
COPY splash/ /app/splash/
COPY docs/ /app/docs/

ENV SIM_MODE=true
ENV SIM_HOST=sitl
ENV SIM_PORT=14551

EXPOSE 8888

# Run telemetry WS server (can also run MCP server)
CMD ["python3", "-m", "splash.control.telemetry_ws_server", "--with-mavlink"]
