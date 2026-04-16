# Dockerfile for PX4 SITL SIH (Software-In-Hardware) simulation
# Wave 1 D4.1: Lightweight simulation tier for Project Avatar

FROM python:3.12-slim-bookworm

ARG PX4_TAG=v1.14.3
ENV DEBIAN_FRONTEND=noninteractive
ENV SIH_VEHICLE_TARGET=sihsim_quadx

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    cmake \
    ninja-build \
    build-essential \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Clone PX4-Autopilot
WORKDIR /px4
RUN git clone --depth 1 --branch ${PX4_TAG} https://github.com/PX4/PX4-Autopilot.git .

# Verify SIH_VEHICLE_TARGET is set
RUN bash -lc 'test -n "${SIH_VEHICLE_TARGET}"'

# Build PX4 SITL with SIH vehicle target
RUN make px4_sitl_default ${SIH_VEHICLE_TARGET}

# Install avatar package
WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir -e .

# Expose MAVLink UDP port
EXPOSE 14540/udp

# Entrypoint script
ENTRYPOINT ["/app/docker/sim-sih/entrypoint.sh"]
