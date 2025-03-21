# to reduce the CI pipeline drastical
FROM tweigeldev/wurzel:beta

# --------------------------
# COPY requirements.txt requirements.txt
# RUN pip install -r requirements.txt
COPY pipeline.py .
# adressing the last step
ENV WURZEL_PIPELINE=".pipeline:pipeline"





