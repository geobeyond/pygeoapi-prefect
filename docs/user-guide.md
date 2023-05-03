# User Guide

## Installation


## Enabling the pygeoapi-prefect process manager

The process manager provided by this project can be enabled by tweaking the pygeoapi configuration file. Use the
`server.manager` property to specify that pygeoapi shall use this instead of its default process manager

```yaml
# pygeoapi config file

server:
  ...
  manager:
    name: pygeoapi_prefect.manager.PrefectManager
```


## Running standard pygeoapi processes

Pre-existing pygeoapi processes can simply be run by the `pygeoapi-prefect` pygeoapi process manager without any
modification. When using this option, processes are always run locally, and it is not possible to use prefect features
other than its ephemeral API and the UI for monitoring execution of processes. Other prefect features such as
deployments, storage, blocks


## Running prefect-powered processes

Define your pygeoapi processes as prefect flows and take full advantage of prefect features like deployments.

This requires:

- defining a pygeoapi process
- defining a prefect flow
- defining a prefect deployment


### Defining prefect-powered processes

Prefect-powered processes need to inherit from `pygeoapi_prefect.process.base.BasePrefectProcessor`, which itself
derives from pygeoapi's `BaseProcessor`.

They have two additional properties, which can be specified for each process in the pygeoapi config file:

- `deployment_info`
- `result_storage_block`


#### Storing process execution results

As we have seen pygeoapi processes are just a think layer on top of regular prefect flows. However, because pygeoapi
expects to be able to retrieve job execution results, there are some special requirements that your custom flows must
conform to. This means that, in order to be able to find flow run execution results:

- the flow must persist its outputs using prefect storage blocks
- the flow must return a `pygeoapi.models.processes.JobStatusInfoInternal`, specifying where the generated outputs have
  been stored
- the flow must be run with `persist_results=True` in order to have prefect store the `JobStatusInfoInternal`, which
  is what we later use to figure out where our actual (file-based) results are and retrieve them


### Using prefect deployments and storage blocks

This example shall use minIO to store data. Let's start by standing up a local docker container with minIO:

```shell
mkdir -p ~/minio/data

docker run \
    --publish 9000:9000 \
    --publish 9090:9090 \
    --name minio \
    --volume ~/minio/data:/data \
    --env "MINIO_ROOT_USER=tester" \
    --env "MINIO_ROOT_PASSWORD=12345678" \
    quay.io/minio/minio \
    server /data --console-address ":9090"
```

Login to the minIO dashboard at http://127.0.0.1:9090 then go ahead and create a bucket named `pygeoapi-test`

Now you need to create a storage block that references this bucket. Either use the custom pygeoapi-prefect CLI command
or create the block using Prefect dashboard. With the CLI command:

```shell
poetry run pygeoapi-prefect create-storage-block \
    test-sb1 \
    s3://pygeoapi-test \
    http://localhost:9000 \
    tester \
    12345678
```

Using the Prefect CLI You may create a block of type *Remote File System*:

- name: `test-sb1`
- basepath: `s3://pygeoapi-test`
- settings:
  ```json
  {
    "key": "tester",
    "secret": "12345678",
    "client_kwargs": {
      "endpoint_url": "http://localhost:9000"
    }
  }
  ```

After having created the block in prefect, we can now deploy our pygeoapi process:

```shell
PYGEOAPI_CONFIG=example-config.yml poetry run pygeoapi-prefect deploy-process-as-flow hi-prefect-world
```

This results in prefect creating a deployment named `hi-prefect-world/test`, and since we are specifying a storage
block, prefect also uploads the flow code onto the storage (which is the minIO bucket created previously).

```shell

# this shall show our deployment name
poetry run prefect deployment ls

poetry run prefect deployment inspect hi-prefect-world/test
```

We should now be able to run our deployment - first by using the prefect CLI:

```shell
poetry run prefect deployment run hi-prefect-world/minio \
  --param name=johnny \
  --param message=wazaaap \
  --param pygeoapi_job_id=test-id-1
```

Then from the prefect dashboard, by selecting the deployment and clicking on _Run -> Custom run..._ (where we can
specify values for the flow parameters, just as we did before in the CLI example)

Finally, we ought to be able to trigger a run of this deployment by leveraging pygeoapi's support for OAPI - Processes:

```shell
http -v localhost:5000/processes/hi-prefect-world/execution inputs:='{"name": "Frankie Four-fingers"}'
```
