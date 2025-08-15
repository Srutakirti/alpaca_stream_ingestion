FROM quay.io/jupyter/base-notebook

# 1. Install Java 17
USER root
RUN apt-get update && apt-get install -y openjdk-17-jdk && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
ENV PATH="$JAVA_HOME/bin:$PATH"

# 2. Switch back to notebook user
USER jovyan

# 3. Install Python deps including pyspark
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# 4. Set SPARK_HOME from pip-installed pyspark
# ENV SPARK_HOME=/opt/conda/lib/python3.*/site-packages/pyspark
# ENV PATH="$SPARK_HOME/bin:$PATH"
