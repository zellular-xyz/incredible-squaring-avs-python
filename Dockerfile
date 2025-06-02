FROM python:3.12
WORKDIR /app
RUN apt-get update && apt-get install -y cmake clang

# Install MCL
RUN wget https://github.com/herumi/mcl/archive/refs/tags/v1.93.zip \
    && unzip v1.93.zip \
    && cd mcl-1.93 \
    && mkdir build \
    && cd build \
    && cmake -DCMAKE_CXX_COMPILER=clang++ .. \
    && make -j8 \
    && make install \
    && cd /app \
    && rm -rf mcl-1.93 v1.93.zip
RUN pip install black mypy flake8
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
RUN pip install -e .
