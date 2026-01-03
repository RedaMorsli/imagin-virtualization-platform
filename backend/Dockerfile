FROM python:3.11-slim

# Install tools needed for k3d install script
RUN apt-get update \
 && apt-get install -y --no-install-recommends wget bash ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Install kubectl CLI
RUN set -e; \
    KUBECTL_VERSION="$(wget -qO- https://dl.k8s.io/release/stable.txt)"; \
    wget -q -O /usr/local/bin/kubectl "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/amd64/kubectl"; \
    chmod +x /usr/local/bin/kubectl

# Install k3d CLI
RUN wget -q -O - https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh | bash

# Set workdir and copy app files
WORKDIR /app
COPY . .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt


# Default command
CMD ["python", "main.py"]
