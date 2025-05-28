FROM python:3.9-slim

WORKDIR /app

# Copy requirements and setup files
COPY requirements.txt .
COPY setup.py .
COPY src/ ./src/

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install -e .

# Create necessary directories for AWS credentials
RUN mkdir -p /root/.aws
RUN mkdir -p /root/cow

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Default command
ENTRYPOINT ["CostMinimizer"]
CMD  ["--configure", "--auto-update-conf"]

# example of docker execution command
# CostExplorer :
#               docker run -it -v $HOME/.aws:/root/.aws -v $HOME/cow:/root/cow -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_SESSION_TOKEN costminimizer --ce
# ComputeOptimizer :
#               docker run -it -v $HOME/.aws:/root/.aws -v $HOME/cow:/root/cow -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_SESSION_TOKEN costminimizer --co
# docker run -it -v $HOME/.aws:/root/.aws -v $HOME/cow:/root/cow -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_SESSION_TOKEN --entrypoint /bin/bash costminimizer
