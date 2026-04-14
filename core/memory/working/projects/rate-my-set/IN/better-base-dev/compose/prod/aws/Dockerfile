# syntax=docker/dockerfile:1.22.0
FROM amazon/aws-cli:2.34.15

COPY --chmod=755 ./compose/prod/aws/maintenance/ /usr/local/bin/
COPY ./compose/prod/postgres/maintenance/_sourced/ /usr/local/bin/_sourced/
