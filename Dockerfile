FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PYTHONPATH=src
EXPOSE 8501
# Collecte initiale puis dashboard
CMD python -m avis_pipeline.cli --pages 3 && streamlit run dashboard.py --server.address 0.0.0.0
