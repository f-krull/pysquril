FROM ubuntu:22.04

RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y \
  make \
  postgresql-common \
  postgresql-14 \
  python3.10-venv

RUN useradd -ms /bin/bash dev-user

USER dev-user
