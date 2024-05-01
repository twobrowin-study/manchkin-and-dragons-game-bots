FROM ubuntu:jammy-20240227 AS builder

RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y wget gnupg \
 && wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | apt-key add - \
 && echo 'deb http://apt.postgresql.org/pub/repos/apt/ jammy-pgdg main' >> /etc/apt/sources.list

RUN apt-get install software-properties-common -y \
 && add-apt-repository ppa:deadsnakes/ppa -y \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y python3.12-full python3-pip

RUN pip install poetry==1.7.1

ENV GAME_HOME="/opt/docker-game"

WORKDIR ${GAME_HOME}

COPY pyproject.toml poetry.lock poetry.toml ./
RUN poetry config virtualenvs.in-project true && \
    poetry install --no-root --no-cache --no-interaction

FROM ubuntu:jammy-20240227

LABEL maintainer="Dubrovin Egor <dubrovin.en@ya.ru>"

ENV GAME_HOME="/opt/docker-game" \
    GAME_DATA="/var/opt/game" \
    GAME_LOGS="/var/log/game"

RUN mkdir -p ${GAME_HOME} ${GAME_DATA} ${GAME_LOGS}

ENV PG_VERSION=15 \
    PG_USER=postgres \
    PG_HOME=/var/lib/postgresql \
    PG_RUNDIR=/run/postgresql \
    PG_LOGDIR=${GAME_LOGS}/postgresql \
    PG_CERTDIR=/etc/postgresql/certs

ENV PG_BINDIR=/usr/lib/postgresql/${PG_VERSION}/bin \
    PG_DATADIR=${GAME_DATA}/postgres

COPY --from=builder /etc/apt/trusted.gpg  /etc/apt/trusted.gpg
COPY --from=builder /etc/apt/sources.list /etc/apt/sources.list

RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y acl sudo locales wget \
      postgresql-${PG_VERSION} postgresql-client-${PG_VERSION} postgresql-contrib-${PG_VERSION} \
 && update-locale LANG=C.UTF-8 LC_MESSAGES=POSIX \
 && locale-gen en_US.UTF-8 \
 && DEBIAN_FRONTEND=noninteractive dpkg-reconfigure locales \
 && ln -sf ${PG_DATADIR}/postgresql.conf /etc/postgresql/${PG_VERSION}/main/postgresql.conf \
 && ln -sf ${PG_DATADIR}/pg_hba.conf /etc/postgresql/${PG_VERSION}/main/pg_hba.conf \
 && ln -sf ${PG_DATADIR}/pg_ident.conf /etc/postgresql/${PG_VERSION}/main/pg_ident.conf \
 && rm -rf ${PG_HOME} \
 && rm -rf /var/lib/apt/lists/*

ENV MINIO_RELEASE="RELEASE.2024-04-18T19-09-19Z" \
    MINIO_DATADIR=${GAME_DATA}/minio \
    MINIO_BINARY=/sbin/minio \
    MINIO_USER=minio

RUN wget https://dl.min.io/server/minio/release/linux-amd64/minio.${MINIO_RELEASE} -O ${MINIO_BINARY} && \
    chmod +x ${MINIO_BINARY} && \
    useradd -ms /bin/bash ${MINIO_USER} -G ${PG_USER}

ENV VIRTUAL_ENV=${GAME_HOME}/.venv \
    PATH="${VIRTUAL_ENV}/bin:$PATH" \
    BOT_MASTER_USER=game-master \
    BOT_COLOR_USER=game-color \
    BOT_DOORS_USER=game-doors \
    BOT_GOSSIP_USER=game-gossip \
    BOT_HERO_USER=game-hero \
    BOT_STAFF_USER=game-staff \
    BOT_STATION_USER=game-station

RUN apt-get update && apt-get install software-properties-common libzbar0 -y \
 && add-apt-repository ppa:deadsnakes/ppa -y \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y python3.12 python3-pil \
 && DEBIAN_FRONTEND=noninteractive apt-get purge -y software-properties-common \
 && rm -rf /var/lib/apt/lists/*

WORKDIR ${GAME_HOME}

COPY --from=builder ${VIRTUAL_ENV} ${VIRTUAL_ENV}

RUN useradd -ms /bin/bash ${BOT_MASTER_USER} && \
    useradd -ms /bin/bash ${BOT_COLOR_USER} && \
    useradd -ms /bin/bash ${BOT_DOORS_USER} && \
    useradd -ms /bin/bash ${BOT_GOSSIP_USER} && \
    useradd -ms /bin/bash ${BOT_HERO_USER} && \
    useradd -ms /bin/bash ${BOT_STAFF_USER} && \
    useradd -ms /bin/bash ${BOT_STATION_USER}

ADD  src    src/
ADD  config config/
COPY pyproject.docker.toml ./pyproject.toml

RUN ${VIRTUAL_ENV}/bin/pip install -e .

COPY runtime/      ./
COPY entrypoint.sh /sbin/entrypoint.sh
RUN  chmod 755     /sbin/entrypoint.sh \
  && chmod 755     ./box-bot

EXPOSE 5432/tcp 9000/tcp 9001/tcp

VOLUME ["/var/opt/game"] 

ENTRYPOINT ["/sbin/entrypoint.sh"]
