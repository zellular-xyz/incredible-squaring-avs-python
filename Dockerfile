FROM python:3.12
WORKDIR /app
RUN apt-get update && apt-get install -y cmake clang curl

# Install Foundry (includes anvil)
RUN curl -L https://foundry.paradigm.xyz | bash
ENV PATH="/root/.foundry/bin:${PATH}"
RUN /root/.foundry/bin/foundryup

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

# Install the project in editable mode
COPY pyproject.toml .
RUN pip install --no-cache-dir -e .[dev]

# Copy the entire project
COPY . .

# Default command
CMD ["make", "test"]
