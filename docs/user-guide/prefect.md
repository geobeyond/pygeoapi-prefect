# Run prefect

!!! Note

    Prefect uses a hybrid model whereby the orchestration components are separated from the
    execution ones.

    This means that it is possible to use a hosted prefect server
    (_i.e._ [prefect cloud](https://app.prefect.cloud/))
    for the orchestration and use your own infrastructure (local, cloud, docker, k8s) for execution.
    This ensures your data stays private.

In order to take full advantage of pygeoapi-prefect, you will need to run (or have access to)
both the following prefect components:

- **prefect server** - This is the main component of prefect's orchestration layer. It features web user
  interface which can be used to monitor flow run execution. It can be run either on your own
  infrastructure or on prefect cloud. For example, in order to launch it locally:

    ```shell
    prefect server start
    ```

  The web UI will now be accessible at http://127.0.0.1:4200

- **prefect agent** - This must be running on your infrastructure
