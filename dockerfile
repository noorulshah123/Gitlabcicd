RUN apt-get update && apt-get install -y --no-install-recommends unzip curl \
 && curl -fsSL https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip -o /tmp/awscliv2.zip \
 && unzip -q /tmp/awscliv2.zip -d /tmp \
 && /tmp/aws/install --bin-dir /usr/local/bin --install-dir /usr/local/aws-cli \
 && rm -rf /var/lib/apt/lists/* /tmp/aws*
# ensure conda's wrapper can't shadow v2
RUN rm -f /opt/conda/envs/py-runtime/bin/aws || true