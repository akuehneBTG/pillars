FROM ubuntu:18.04
ENV DEBIAN_FRONTEND=noninteractive 
RUN mkdir /repos
WORKDIR /repos
RUN apt-get update && apt-get -y upgrade
RUN apt-get -y install python3.7 python3-pip  git
RUN git clone https://github.com/akuehneBTG/pillars.git
WORKDIR /repos/pillars
RUN chmod 755 ./cert
RUN python3.7 -m pip install --upgrade pip
RUN pip3.7 install -r requirements.txt
ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8
EXPOSE 80
ENTRYPOINT python3.7 pillars.py
