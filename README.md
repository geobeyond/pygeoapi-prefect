# pygeoapi-prefect

A process manager for [pygeoapi] that uses [prefect].


[pygeoapi]: https://pygeoapi.io/
[prefect]: https://www.prefect.io/


## Installation

In time, this project will be available in the python package index (AKA pypi) and be installable via pip, but for 
now you can install it by git cloning and then using poetry to install


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


## Usage

This project implements a pygeoapi process manager that uses prefect. It enables you to run two different types of
processes:

- Standard pygeoapi processes
- Prefect-powered processes


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

### Defining 


## Development

Install this project with poetry

```shell
git clone
poetry install --with dev
```

Start the prefect server:

```shell
poetry run prefect server start
```

Update the prefect config, as directed by the prefect server:

```shell
poetry run prefect config set PREFECT_API_URL=http://127.0.0.1:4200/api
```

If you want to deploy a pygeoapi process locally with prefect, then also start a prefect agent:

```shell
poetry run prefect agent start --work-queue pygeoapi
```

Now stand up pygeoapi with the provided config files:

```shell
PYGEOAPI_CONFIG=example-config.yml PYGEOAPI_OPENAPI=example-openapi.yml poetry run pygeoapi serve
```

If you need to regenerate the openapi description file, run:

```shell
poetry run pygeoapi openapi generate example-config.yml > example-openapi.yml
```

Deploy the `hi-prefect-world` process:

```shell
poetry run pygeoapi-prefect deploy-as-prefect-flow hi-prefect-world
```

- Run a deployed process with prefect

```shell
poetry run prefect deployment run --param 
```


- List processes

  ```shell
  http -v localhost:5000/processes
  ```

- Execute the standard `hello-world` process via prefect:

  ```shell
  http -v localhost:5000/processes/hello-world/execution inputs:='{"message": "Yo", "name": "planet Earth"}'
  ```

- Execute our `hi-prefect-world` process:

  ```shell
  http -v localhost:5000/processes/hi-prefect-world/execution inputs:='{"message": "Yo", "name": "planet Earth"}'
  ```


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

Now go to the prefect dashboard and create a storage block that references this bucket. You may create a block of type
*Remote File System*:

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
PYGEOAPI_CONFIG=example-config.yml poetry run pygeoapi-prefect deploy-process-as-flow \
  hi-prefect-world \
  --prefect-queue-name=test \
  --deployment-name=test \
  --storage-block-name=remote-file-system/test-sb1
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