# Spec §11.1: serwer modelu (Ollama). Wersja i digest obrazów przypięte, proces na własnym
# użytkowniku zamiast root. Modele w wolumenie /home/ollama/.ollama.
#
# Targety:
#   cpu (domyślny, ostatni etap) - czyste ubuntu:24.04 + binarka ollama i biblioteki CPU
#       (ggml, llama.cpp: MIT). Bez bibliotek NVIDIA CUDA/cuDNN z obrazu producenta
#       (licencja własnościowa NVIDIA, ok. 4,4 GB, na CPU nieużywane).
#   gpu - obraz producenta z CUDA, tylko przez docker-compose.gpu.yml.
#
# Ollama szuka bibliotek w ../lib/ollama względem binarki, więc układ /usr/bin + /usr/lib
# zostaje taki jak w obrazie producenta.

FROM ollama/ollama:0.40.16@sha256:910d0d8107b538fb0894e63163eb195de0cc7aefcbc666dc62d3b18f71124592 AS upstream

# Biblioteki dla CPU: bez katalogów CUDA (cuda_v12, cuda_v13, mlx_cuda_v13), nagłówków CUDA
# i backendu Vulkan (wymaga sterowników GPU z mesa i libvulkan, na CPU nieużywany).
FROM upstream AS cpu-files
RUN cp -a /usr/lib/ollama /tmp/ollama-lib \
 && cd /tmp/ollama-lib \
 && rm -rf cuda_v12 cuda_v13 mlx_cuda_v13 include vulkan \
        CUDNN_LICENSE.txt CUTLASS_LICENSE.txt NVTX3_LICENSE.txt MLX_LICENSE MLX_C_LICENSE

FROM upstream AS gpu
RUN useradd --system --uid 10002 --user-group --create-home --home-dir /home/ollama \
        --shell /usr/sbin/nologin ollama \
 && mkdir -p /home/ollama/.ollama/models \
 && chown -R ollama:ollama /home/ollama/.ollama
COPY --chmod=0755 pull-model.sh /usr/local/bin/pull-model
ENV HOME=/home/ollama OLLAMA_HOST=0.0.0.0:11434
USER ollama
EXPOSE 11434

FROM ubuntu:24.04@sha256:9c7f200c07e3d4a03e7249d2c16bf66a51120fb876aa2242cf31451412543289 AS cpu
# ca-certificates: TLS przy jednorazowym pobieraniu modelu (llm-pull).
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --system --uid 10002 --user-group --create-home --home-dir /home/ollama \
        --shell /usr/sbin/nologin ollama \
 && mkdir -p /home/ollama/.ollama/models \
 && chown -R ollama:ollama /home/ollama/.ollama
COPY --from=upstream /usr/bin/ollama /usr/bin/ollama
COPY --from=cpu-files /tmp/ollama-lib /usr/lib/ollama
COPY --chmod=0755 pull-model.sh /usr/local/bin/pull-model
LABEL org.opencontainers.image.title="coi-cf-llm" \
      org.opencontainers.image.version="0.40.16"
ENV HOME=/home/ollama OLLAMA_HOST=0.0.0.0:11434
USER ollama
EXPOSE 11434
ENTRYPOINT ["/usr/bin/ollama"]
CMD ["serve"]
