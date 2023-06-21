# Deploying a process

In order to be able to take advantage of full prefect capabilities, flows must be deployed. A deployed flow can be
scheduled and triggered via the prefect API. When a flow is deployed it becomes possible to:

- Schedule it
- Create ad-hoc flow runs via the prefect API or UI
- Upload flow files to a defined storage location, for retrieval at runtime
- Specify runtime infrastructure for flow runs, such as Docker or Kubernetes configuration

A prefect deployment thus stores metadata about the storage location of a flow's code and how it should be run.

Deployments are inspected by the prefect agent when it is time to run a scheduled flow. these are used by the agent to:

- Retrieve flow code from it storage location and make it available for execution
- Set up a suitable execution environment for the flow run. For example: spin up a docker container and install Python
  dependencies

!!! NOTE

    If a flow has not been deployed, then it can only run locally. This is why pygeoapi-prefect is
    able to run vanilla pygeoapi processes - it wraps them in a flow at runtime and calls them, making their execution
    local.


## Deploying pygeoapi-prefect flows

pygeoapi-prefect contains a CLI command that can be used to deploy previously configured pygeoapi processes. This
command reads in the pygeoapi configuration and is able to create a suitable deployment from the configuration of
the relevant process, as mentioned in [defining processes](defining-processes.md#enable-process-in-pygeoapi).

```shell
export PYGEOAPI_CONFIG=my-pygeoapi-config.yml

pygeoapi plugins prefect deploy-process <process-id>
```


### Using prefect to deploy a pygeoapi-prefect process

In addition to the custom pygeoapi-prefect CLI command, it is also possible to use the standard prefect CLI commands
to create deployments. Note however that when using these prefect CLI commands the pygeoapi configuration is ignored.
