# Spec §11.1: oficjalny obraz Ollama (wersja i digest przypięte), proces na własnym
# użytkowniku zamiast root. Modele w wolumenie /home/ollama/.ollama.
FROM ollama/ollama:0.40.16@sha256:910d0d8107b538fb0894e63163eb195de0cc7aefcbc666dc62d3b18f71124592
# Katalog modeli istnieje w obrazie z właścicielem `ollama`: nowy wolumen nazwany przejmuje
# te uprawnienia przy pierwszym montowaniu.
RUN useradd --system --uid 10002 --user-group --create-home --home-dir /home/ollama \
        --shell /usr/sbin/nologin ollama \
 && mkdir -p /home/ollama/.ollama/models \
 && chown -R ollama:ollama /home/ollama/.ollama
COPY --chmod=0755 pull-model.sh /usr/local/bin/pull-model
ENV HOME=/home/ollama OLLAMA_HOST=0.0.0.0:11434
USER ollama
EXPOSE 11434
