FROM ubuntu:22.04


# note: the below is adapted from my generic ubuntu base dockerfile, and could be simplified



ARG DEBIAN_FRONTEND=noninteractive
ENV TZ=Europe/Prague
ARG TERM=linux
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone
RUN echo 'debconf debconf/frontend select Noninteractive' | debconf-set-selections


RUN apt-get update
RUN apt-get install -y ca-certificates apt-utils tzdata time locales language-pack-en unattended-upgrades tzdata time apt-utils dialog 2>&1 | \
    grep -v "^debconf: delaying package configuration.*"
    

ENV LOC en_US.UTF-8
ENV LANG $LOC
ENV LANGUAGE $LANG
ENV LC_ALL $LOC


RUN sed -i -e 's/# $LOC UTF-8/$LOC UTF-8/' /etc/locale.gen
RUN dpkg-reconfigure --frontend=noninteractive locales  && update-locale LANG=$LOC
RUN unattended-upgrade


RUN mkdir /app
RUN apt-get install -y git python3 python3-dev python3-pip python3-wheel libcurl4-gnutls-dev libssl-dev libgnutls28-dev curl


ARG uid=1000
ARG gid=1000
RUN groupadd -g $gid myuser && useradd -lm -u $uid -g $gid myuser
RUN chown -vR myuser:myuser /home/myuser
RUN ls -thrlsa /home/myuser/


ENV PATH=$PATH:/home/myuser/.local/bin

ENV PYTHONUNBUFFERED true
ENV PYTHONDONTWRITEBYTECODE 1



COPY requirements.txt /app
COPY *py /app
WORKDIR /app
RUN pip install -r requirements.txt
CMD ["python3", "main.py"]

USER myuser
