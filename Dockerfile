# This file is only used to get a python docker container for the prepare script
FROM openjdk:18-alpine3.15
# we do need java to check java files for usability

RUN addgroup --gid 1000 preparer && adduser --uid 1000 --ingroup preparer --home /home/preparer --disabled-password preparer
RUN apk add --update --no-cache python3 bash
RUN python3 -m ensurepip
RUN ln -s /usr/bin/python3 /usr/bin/python && ln -s /usr/bin/pip3 /usr/bin/pip
RUN /usr/bin/python3 -m pip install --no-cache --upgrade pip wheel

COPY requirements.txt /
RUN pip3 install -r /requirements.txt

USER preparer
WORKDIR /home/preparer

ENTRYPOINT [ "python3", "prepare.py" ]

COPY prepare.py /root/
COPY check_compile_java.sh /