# This file is only used to get a python docker container for the prepare script
FROM python:3.10.2-alpine3.15

RUN addgroup --gid 1000 preparer && adduser --uid 1000 --ingroup preparer --home /home/preparer --disabled-password preparer

USER preparer
WORKDIR /home/preparer

ENTRYPOINT [ "python3", "prepare.py" ]

COPY prepare.py /root/