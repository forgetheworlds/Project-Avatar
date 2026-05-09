# Dockerfile for PX4 SITL with Gazebo Harmonic simulation
# Wave 1 D4.2: Full physics simulation tier for Project Avatar

FROM --platform=linux/amd64 ubuntu:24.04

ARG PX4_TAG=v1.14.3
ENV DEBIAN_FRONTEND=noninteractive
ENV LIBGL_ALWAYS_SOFTWARE=1

# Install build dependencies and Gazebo prerequisites
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    cmake \
    ninja-build \
    build-essential \
    python3-pip \
    gnupg \
    lsb-release \
    wget \
    curl \
    xvfb \
    mesa-utils \
    && rm -rf /var/lib/apt/lists/*

# Install Gazebo Harmonic
RUN wget https://packages.osrfoundation.org/gazebo.gpg -O /usr/share/keyrings/pkgs-osrf-archive-keyrings.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/pkgs-osrf-archive-keyrings.gpg] http://packages.osrfoundation.org/gazebo/ubuntu-stable $(lsb_release -cs) main" | tee /etc/apt/sources.list.d/gazebo-stable.list > /dev/null \
    && apt-get update \
    && apt-get install -y gz-harmonic gz-sim8-cli \
    && rm -rf /var/lib/apt/lists/*

# Clone and build PX4-Autopilot with Gazebo support
WORKDIR /px4
RUN git clone --depth 1 --branch ${PX4_TAG} https://github.com/PX4/PX4-Autopilot.git . \
    && make px4_sitl gz_x500

# Install avatar package
WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir -e .

# Expose MAVLink UDP port
EXPOSE 14540/udp

# Entrypoint script
ENTRYPOINT ["/app/docker/sim-gazebo/entrypoint.sh"]
