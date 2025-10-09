# -------- Stage 1: build the conda env (no awscli inside) --------
FROM continuumio/miniconda3:24.7.1 AS builder
SHELL ["/bin/bash","-lc"]
USER root

# Copy specs
COPY app-runtime-python/environment.yml /tmp/environment.yml
COPY app-runtime-python/requirements.txt /tmp/requirements.txt
# (optional) pip.conf for your proxy/CA
COPY pip.conf /etc/pip.conf
RUN chmod 644 /etc/pip.conf || true

# Create env
RUN conda config --set channel_priority strict && \
    conda env create -n py-runtime -f /tmp/environment.yml && \
    conda run -n py-runtime pip install --no-cache-dir -r /tmp/requirements.txt && \
    conda clean -afy

# -------- Stage 2: final runtime --------
FROM python:3.10.14-slim-bookworm
SHELL ["/bin/bash","-lc"]

# System deps and AWS CLI v2 (bundled)
RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates curl unzip && \
    update-ca-certificates && \
    curl -fsSL https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip -o /tmp/awscliv2.zip && \
    unzip -q /tmp/awscliv2.zip -d /tmp && \
    /tmp/aws/install --bin-dir /usr/local/bin --install-dir /usr/local/aws-cli && \
    rm -rf /var/lib/apt/lists/* /tmp/aws*

# Your enterprise root CA (keep if you need it)
COPY cloudguard-root.crt /usr/local/share/ca-certificates/cloudguard-root.crt
RUN chmod 644 /usr/local/share/ca-certificates/cloudguard-root.crt && update-ca-certificates

# Bring in the conda env
COPY --from=builder /opt/conda/envs/py-runtime /opt/conda/envs/py-runtime

# Ensure CLI v2 wins over any python shim
ENV PATH="/usr/local/bin:/opt/conda/envs/py-runtime/bin:${PATH}"
RUN rm -f /opt/conda/envs/py-runtime/bin/aws* || true

# TLS + boto hardening
ENV REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt \
    SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt \
    CURL_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt \
    AWS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt \
    BOTO_DISABLE_PYOPENSSL=1 \
    AWS_EC2_METADATA_DISABLED=true \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# App user + workdir
RUN useradd -m -s /bin/bash shinyuser
WORKDIR /home/shinyuser

# Entrypoint
COPY --chown=shinyuser:shinyuser app-runtime-python/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

EXPOSE 8080 3838 8000 7860 8501
ENV PORT=8080 APP_DIR=/home/shinyuser
USER shinyuser
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
