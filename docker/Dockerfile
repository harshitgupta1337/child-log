FROM python:3.11

SHELL ["/bin/bash", "-c"]

RUN git clone https://github.com/harshitgupta1337/child-log.git && \
  cd child-log && git submodule update --init

RUN cd child-log && python3 -m venv .venv && \
  source .venv/bin/activate && pip install -r requirements.txt

RUN curl -sSL https://ngrok-agent.s3.amazonaws.com/ngrok.asc \
  | tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null \
  && echo "deb https://ngrok-agent.s3.amazonaws.com bookworm main" \
  | tee /etc/apt/sources.list.d/ngrok.list \
  && apt -y update \
  && apt -y install ngrok

RUN apt install -y jq

ADD app-runner.sh /
ADD ngrok-daemon.sh /
ADD master.sh /
