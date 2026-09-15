# Use an official lightweight Python image
FROM python:3.11-slim

# Set environment variables
# Prevents Python from writing pyc files to disc
ENV PYTHONDONTWRITEBYTECODE=1
# Prevents Python from buffering stdout and stderr
ENV PYTHONUNBUFFERED=1
# Encourage glibc to return freed memory to the OS
ENV MALLOC_TRIM_THRESHOLD_=65536
# Use the system allocator for more efficient large allocations
ENV PYTHONMALLOC=malloc

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file to the working directory
COPY requirements.txt .

# Install AWS CLI and Python dependencies
RUN apt-get update && \
    apt-get install -y awscli && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code to the container
COPY . .

# Create necessary directories (in case they are missing or ignored by git)
RUN mkdir -p docs db/chroma_db

# Expose the port that the FastAPI app runs on
EXPOSE 8000

# Command to run the application using Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
