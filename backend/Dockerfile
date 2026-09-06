# syntax=docker/dockerfile:1.7
#
# TRACE backend — development / CI image.
#
# Three stages so the two expensive, slow-changing layers (the dependency set
# and the model weights) cache independently of the application code:
#
#   builder  installs the locked dependency set into /opt/venv
#   models   uses that venv to download the model weights into /opt/models
#   runtime  slim base + the native binaries + both of the above + the app
#
# Pinned to linux/amd64 at every stage. torch, the Tesseract packages and the
# manylinux wheels this lockfile resolves to are all platform-specific, so an
# arm64 host must emulate rather than silently produce a different image.

# 3.14.5 is the interpreter requirements.lock.txt was resolved and verified
# against. Bookworm (Debian 12) rather than trixie: glibc 2.36 satisfies the
# manylinux_2_28 wheels this lockfile uses, and the Tesseract language packages
# keep their long-standing names.
ARG PYTHON_VERSION=3.14.5
ARG PYTHON_BASE=python:${PYTHON_VERSION}-slim-bookworm


# ---------------------------------------------------------------------------
# Stage 1 — builder: the locked dependency set, in a relocatable venv.
# ---------------------------------------------------------------------------
FROM --platform=linux/amd64 ${PYTHON_BASE} AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Every compiled dependency in the lockfile publishes a cp314 or abi3
# manylinux x86_64 wheel, so nothing here should need to compile. A compiler is
# kept anyway for the handful of pure-Python packages that ship only an sdist
# (langdetect among them) and therefore still run a setup.py.
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential \
 && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"
RUN pip install --upgrade pip setuptools wheel

WORKDIR /build
COPY requirements.lock.txt ./

# torch first, from PyTorch's CPU-only index.
#
# The default PyPI torch bundles the CUDA runtime — several GB of nvidia-*
# wheels that nothing here can use: this service runs sentence-transformers on
# CPU and the image has no GPU. The CPU build is the same torch without them.
#
# The pin is read out of the lockfile rather than written twice, so the two
# cannot drift. PEP 440 makes "2.13.0+cpu" satisfy "torch==2.13.0", so the
# lockfile install below sees it as already present and leaves it alone.
RUN TORCH_PIN="$(grep -i -E '^torch==' requirements.lock.txt)" \
 && test -n "${TORCH_PIN}" \
 && echo "Installing ${TORCH_PIN} from the CPU index" \
 && pip install --index-url https://download.pytorch.org/whl/cpu "${TORCH_PIN}"

# Fail the build rather than ship a multi-gigabyte image full of dead CUDA
# libraries because the index URL stopped being honoured.
RUN python -c "import torch, sys; v = torch.__version__; print('torch', v); sys.exit(0 if v.endswith('+cpu') else 'expected a +cpu build, got ' + v)"

# Then the rest of the environment, from requirements.lock.txt.
#
# Not requirements.txt: a fresh resolve of the direct pins drifts across 39
# transitive packages, and the lockfile is the exact set the test suite was
# verified against. "Reproducible" is the whole point of this image.
#
# The lockfile is installed as-is. pywin32 is in it because the lockfile was
# frozen on Windows and has no Linux distribution, but it now carries a
# `sys_platform == "win32"` marker, so pip skips it here rather than failing.
# The marker lives in the lockfile rather than in a grep filter on this line:
# a lockfile that only installs after the Dockerfile edits it is not a
# lockfile, and the defect would stay invisible to anyone who installs it
# directly on Linux or macOS.
RUN pip install -r requirements.lock.txt


# ---------------------------------------------------------------------------
# Stage 2 — models: bake the weights into the image.
# ---------------------------------------------------------------------------
FROM builder AS models

ENV HF_HOME=/opt/models

# Defaults track app/core/config.py (embedding_model_name, rerank_model_name).
# Override both together with the config if the models ever change.
ARG EMBEDDING_MODEL_NAME=all-MiniLM-L6-v2
ARG RERANK_MODEL_NAME=cross-encoder/ms-marco-MiniLM-L-6-v2
ENV EMBEDDING_MODEL_NAME=${EMBEDDING_MODEL_NAME} \
    RERANK_MODEL_NAME=${RERANK_MODEL_NAME}

# Only the script, so editing application code does not re-download ~200MB of
# weights.
COPY scripts/bake_models.py /tmp/bake_models.py

# First pass downloads and exercises both models.
RUN python /tmp/bake_models.py

# Second pass with the hub forced offline. This is the actual guarantee: if
# anything still reaches for huggingface.co, the build fails here instead of
# the first user request timing out in production.
RUN HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 python /tmp/bake_models.py


# ---------------------------------------------------------------------------
# Stage 3 — runtime.
# ---------------------------------------------------------------------------
FROM --platform=linux/amd64 ${PYTHON_BASE} AS runtime

# Native libraries. None of these arrive with a pip install:
#
#   tesseract-ocr        pytesseract is a thin wrapper that shells out to this
#                        binary. Without it every scanned PDF and image yields
#                        empty text and OcrEngine.is_available() returns False.
#   tesseract-ocr-*      One traineddata package per language OcrEngine
#                        accepts (SUPPORTED_LANGUAGES in
#                        app/processing/ocr/engine.py), so any OCR_LANGUAGE the
#                        code validates actually works. eng is the default;
#                        the rest add roughly 70MB in total.
#   libglib2.0-0         opencv-python-headless links against it, and
#                        app/processing/ocr/preprocessing.py imports cv2 at
#                        module scope on the startup import chain — so a
#                        missing libglib is a boot failure, not an OCR failure.
#   libgomp1             OpenMP runtime for torch and scikit-learn.
#   libpq5               libpq for psycopg2-binary, used by Alembic's sync URL.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      tesseract-ocr \
      tesseract-ocr-eng \
      tesseract-ocr-fra \
      tesseract-ocr-deu \
      tesseract-ocr-spa \
      tesseract-ocr-ita \
      tesseract-ocr-por \
      tesseract-ocr-nld \
      tesseract-ocr-ara \
      tesseract-ocr-chi-sim \
      tesseract-ocr-jpn \
      tesseract-ocr-kor \
      libglib2.0-0 \
      libgomp1 \
      libpq5 \
 && rm -rf /var/lib/apt/lists/*

# TESSDATA_PREFIX is deliberately not set: the Debian packages install the
# traineddata where the packaged binary already looks for it, and an explicit
# wrong value is the usual cause of "Failed loading language 'eng'".
RUN tesseract --version && tesseract --list-langs

# Non-root. Fixed uid/gid 1000 so bind-mounted host directories line up with
# the usual first desktop user during development.
RUN groupadd --system --gid 1000 trace \
 && useradd --system --uid 1000 --gid 1000 --create-home --home-dir /home/trace trace

# HF_HUB_OFFLINE/TRANSFORMERS_OFFLINE are on by default, and that is the whole
# point of the models stage. Without them a cached model still costs ~36 HTTP
# round trips to huggingface.co on every boot — sentence-transformers
# revalidates every file it might need — so the container needs outbound
# internet in order to start, and stalls for as long as the Hub takes to
# answer. The weights are already here; nothing should be asked about them.
#
# Stage 2 proves this works: its second pass loads both models with exactly
# these variables set. The consequence is that changing EMBEDDING_MODEL_NAME or
# RERANK_MODEL_NAME without rebuilding now fails loudly instead of quietly
# downloading different weights, which is the safer of the two failures.
ENV PATH="/opt/venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    HF_HOME=/opt/models \
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1 \
    STORAGE_ROOT=/app/storage \
    WORKSPACE_ROOT=/app/workspace

COPY --from=builder /opt/venv /opt/venv
COPY --from=models --chown=trace:trace /opt/models /opt/models

WORKDIR /app

# Created here, before anything mounts over them, on purpose. Docker seeds a
# new named volume from the image's contents *and ownership* at the mount
# point, so creating /app/storage as trace is what lets the non-root process
# write to it. Without that the volume arrives owned by root and every upload
# fails with EACCES.
#
# /app/workspace matters for the same reason but more sharply: Settings
# .workspace_root_path calls mkdir() on access, and its default resolves to
# /workspace — a path outside anything a non-root user may create. WORKSPACE_ROOT
# above points it somewhere writable.
RUN mkdir -p /app/storage /app/workspace

COPY --chown=trace:trace . /app

RUN chown -R trace:trace /app

USER trace

# Import the application at build time. This is the cheap check that catches
# the container-specific failures — a missing libglib behind cv2, a native
# library torch or Tesseract needs — at build rather than at boot. It only
# imports: the lifespan hook, and therefore every network call, does not run.
#
# DATABASE_URL is supplied here because app/db/session.py builds its engine at
# module scope, so importing the app parses the URL — and with no value set
# SQLAlchemy raises before any of the native libraries this check exists to
# test are ever reached. The value is a throwaway: create_async_engine only
# parses the URL and creates a lazy pool, so nothing connects. It is scoped to
# this RUN rather than set as ENV precisely so it cannot become a default that
# masks an unset DATABASE_URL at runtime.
RUN DATABASE_URL="postgresql+asyncpg://build:build@127.0.0.1:5432/build" python -c "import app.main; print('app.main imported OK')"

EXPOSE 8000

# No curl or wget in the slim base, so the probe uses the interpreter that is
# already here. /api/health does no network I/O by design, so this stays cheap.
#
# start-period is generous because startup loads the cross-encoder before
# serving traffic (reranker_service.warmup()); that is seconds from the baked
# cache but should not be raced.
HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=5 \
  CMD python -c "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=8).status == 200 else 1)"

# Migrations are NOT run here. They are a separate one-shot compose service, so
# that starting a second API replica can never race the first into an
# ALTER TABLE, and so schema changes stay a deliberate act rather than a side
# effect of a restart.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
