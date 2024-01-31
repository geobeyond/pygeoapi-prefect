FROM python:3.10-slim-bullseye

# Install security updates and system dependencies, then clean up
RUN export DEBIAN_FRONTEND=noninteractive && \
    apt-get update && \
    apt-get --yes upgrade && \
    # these are our own dependencies and utilities
    # if you need to add more, please sort them in alphabetical order
    apt-get install --yes --no-install-recommends \
      curl \
      net-tools \
      procps \
      tini && \
    apt-get --yes clean && \
    rm -rf /var/lib/apt/lists/*

# download poetry
RUN curl --silent --show-error --location \
    https://install.python-poetry.org > /opt/install-poetry.py

# Create a normal non-root user so that we can use it to run
RUN useradd --create-home appuser

# Compile python stuff to bytecode to improve startup times
RUN python -c "import compileall; compileall.compile_path(maxlevels=10)"

USER appuser

#RUN mkdir /home/appuser/app  && \
#    mkdir /home/appuser/data && \
#    python opt/install-poetry.py --yes --version 1.4.2


RUN mkdir --parents /home/appuser/dev/geobeyond/pygeoapi-prefect  && \
    python opt/install-poetry.py --yes --version 1.4.2

ENV PATH="$PATH:/home/appuser/.local/bin" \
    # This allows us to get traces whenever some C code segfaults
    PYTHONFAULTHANDLER=1

# Copy over pygeoapi source
WORKDIR /home/appuser/dev
COPY --chown=appuser:appuser ../../pygeoapi .

# Only copy the dependencies for now and install them
# WORKDIR /home/appuser/app
WORKDIR /home/appuser/dev/geobeyond/pygeoapi-prefect
COPY --chown=appuser:appuser pyproject.toml poetry.lock ./
RUN poetry install --no-root --only main

EXPOSE 5000

# Now install our code
COPY --chown=appuser:appuser . .
RUN poetry install --only main

# Write git commit identifier into the image
ARG GIT_COMMIT
ENV GIT_COMMIT=$GIT_COMMIT
RUN echo $GIT_COMMIT > /home/appuser/git-commit.txt

# Compile python stuff to bytecode to improve startup times
RUN poetry run python -c "import compileall; compileall.compile_path(maxlevels=10)"

# use tini as the init process
ENTRYPOINT ["tini", "-g", "--", "poetry", "run", "pygeoapi"]

CMD ["serve"]
