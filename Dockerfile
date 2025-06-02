FROM python:3.12
WORKDIR /app
RUN pip install black mypy flake8
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
RUN pip install -e .
