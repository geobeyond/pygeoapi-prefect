# Installation

In time, this project will be available in the python package index (AKA pypi) and be installable via pip, but for
now you can install it by git cloning and then using poetry to install

```shell
git clone https://github.com/geobeyond/pygeoapi-prefect.git
cd pygeoapi-prefect
poetry install
```

Check the [Development](../development.md) section for a more developer oriented
installation procedure


## Enabling the pygeoapi-prefect process manager

After installation, you need to enable the pygeoapi-prefect custom process/job manager for pygeoapi.

This can be done, by modifying the pygeoapi configuration file. Specifically, the `server.manager.name` configuration
parameter needs to be set to `pygeopai_prefect.manager.PrefectManager`.

```yaml
# pygeoapi configuration file
server:
  manager:
    name: pygeoapi_prefect.manager.PrefectManager
```
