FROM python:3.12-slim

COPY requirments.txt .
RUN pip install --no-cache-dir -r requirments.txt
COPY . .

# Copy the .env file
# COPY .env .env

EXPOSE 8000
CMD ["uvicorn", "mongotest:app", "--host", "0.0.0.0", "--port", "8000"]
