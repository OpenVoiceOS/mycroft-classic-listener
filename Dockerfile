FROM ghcr.io/openvoiceos/core:dev

RUN apt-get install -y portaudio19-dev libpulse-dev swig

COPY . /tmp/mycroft-classic-listener
RUN pip3 install https://github.com/alphacep/vosk-api/releases/download/v0.3.43/vosk-0.3.43-py3-none-linux_x86_64.whl
RUN pip3 install /tmp/mycroft-classic-listener

USER mycroft

ENTRYPOINT mycroft-classic-listener
