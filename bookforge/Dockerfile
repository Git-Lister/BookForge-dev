FROM nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV VENV_PATH=/opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

RUN apt-get update && apt-get install -y \
    software-properties-common \
    curl \
    git \
    ffmpeg \
    libsndfile1 \
    build-essential \
    && add-apt-repository ppa:deadsnakes/ppa -y \
    && apt-get update && apt-get install -y \
    python3.11 \
    python3.11-dev \
    python3.11-venv \
    && rm -rf /var/lib/apt/lists/*

RUN python3.11 -m venv $VENV_PATH

RUN pip install --upgrade pip setuptools wheel

RUN pip install "numpy==1.26.4"

RUN pip install \
    torch==2.2.0 torchaudio==2.2.0 --index-url https://download.pytorch.org/whl/cu121 && \
    pip install "transformers==5.0.0" && \
    pip install "coqui-tts==0.27.5"

RUN python -c "import torch; print(torch.__version__)" && \
    python -c "import transformers; print(transformers.__version__)" && \
    python -c "from TTS.api import TTS; print('Coqui import OK')"

COPY requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

COPY . /app

RUN pip install -e .

EXPOSE 8501

CMD ["streamlit", "run", "src/bookforge/ui.py", "--server.address=0.0.0.0", "--server.port=8501"]