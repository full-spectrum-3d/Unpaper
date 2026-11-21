"""Ollama + qwen3.5:35b-a3b na GPU w Modalu, za tym samym API co lokalna Ollama.

Backend nie wymaga zmian: `LLM_BASE_URL` = URL z `modal deploy`, a `LLM_AUTH_KEY` /
`LLM_AUTH_SECRET` = proxy auth token (modal.com → Settings → Proxy Auth Tokens).

Koszty: kontener startuje dopiero przy żądaniu i gaśnie po `SCALEDOWN_S` bez ruchu.
`max_containers=1`, więc nigdy nie działa więcej niż jedno GPU naraz.

    modal run scripts/modal_ollama.py::pull   # raz: pobiera model do Volume (bez GPU)
    modal deploy scripts/modal_ollama.py      # wypisuje URL endpointu
    modal app stop def-ollama                 # po demo: wyłącza endpoint
"""

# ruff: noqa: S603, S607  (stały plik ollama w obrazie, bez danych z zewnątrz)
import subprocess
import time

import modal

MODEL = "qwen3.5:35b-a3b"  # domyślny (LLM_MODEL)
EXTRA_MODELS = ["qwen3:8b"]  # do wyboru (LLM_MODELS)
GPU = "L40S"  # 48 GB, ok. 1.95 $/h; qwen3.5:35b-a3b (Q4) zajmuje ok. 22 GB + KV cache
SCALEDOWN_S = 300  # bezczynny kontener gaśnie po 5 min
PORT = 11434
MODELS_DIR = "/models"

image = (
    modal.Image.from_registry("ollama/ollama:0.40.16", add_python="3.12")
    .entrypoint([])
    .env(
        {
            "OLLAMA_HOST": f"0.0.0.0:{PORT}",
            "OLLAMA_MODELS": MODELS_DIR,
            "OLLAMA_MAX_LOADED_MODELS": "2",  # oba modele naraz w 48 GB
            "OLLAMA_KEEP_ALIVE": "-1",  # model w VRAM, dopóki kontener żyje
        }
    )
)
models = modal.Volume.from_name("def-ollama-models", create_if_missing=True)
app = modal.App("def-ollama", image=image)


def _start_ollama() -> subprocess.Popen[bytes]:
    proc = subprocess.Popen(["ollama", "serve"])
    for _ in range(60):
        if subprocess.run(["ollama", "list"], capture_output=True).returncode == 0:
            return proc
        time.sleep(0.5)
    raise RuntimeError("ollama serve nie wystartował")


@app.function(volumes={MODELS_DIR: models}, timeout=1800)
def pull(names: str = "") -> None:
    """Pobiera modele do Volume, żeby zimny start GPU ich nie ściągał.

    `--names a,b` pobiera inne modele (np. do porównania w llm_eval).
    """
    _start_ollama()
    for name in names.split(",") if names else [MODEL, *EXTRA_MODELS]:
        subprocess.run(["ollama", "pull", name], check=True)
    models.commit()


@app.function(
    gpu=GPU,
    volumes={MODELS_DIR: models},
    min_containers=0,
    max_containers=1,
    scaledown_window=SCALEDOWN_S,
    timeout=600,
)
@modal.concurrent(max_inputs=8)
@modal.web_server(PORT, startup_timeout=120, requires_proxy_auth=True)
def serve() -> None:
    _start_ollama()
    # Ładuje model do VRAM od razu, a nie przy pierwszym żądaniu.
    subprocess.Popen(["ollama", "run", MODEL, ""])
