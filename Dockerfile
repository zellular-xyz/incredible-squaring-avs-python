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

# Install development tools
RUN pip install black mypy flake8

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy the entire project
COPY . .

# Install the project in editable mode
RUN pip install -e .

# Default command
CMD ["make", "test"]
