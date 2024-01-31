# Using prefect deployments and storage blocks

## Configure storage for flow and results

This example shall use minIO, an S3-compatible object store, to store data.
We will configure pygeoapi to use minIO for both:

- Storing process execution outputs
- Storing the deployed flow code

In order to follow along, ensure you have:

- prefect server running
- your local prefect config has `PREFECT_API_URL=<url-of-your-server>`

!!! NOTE

    If you are running prefect by using the supplied `docker/compose.yaml` docker
    compose stack, prefect server will be running locally on port 44200, which is not
    the standard port. In this case it may be easier to create a prefect profile and use
    that:

    ```sh
    # you must have prefect installed locally
    prefect profile create pygeoapi-prefect-dev
    prefect profile use pygeoapi-prefect-dev
    prefect config set PREFECT_API_URL=http://0.0.0.0:44200
    ```


Let's start by standing up a local docker container with minIO:

```shell
mkdir --parents ~/minio/data

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

Now you need to create a prefect storage block that references this bucket. Either use the custom
CLI command shipped by pygeoapi-prefect or create the block using prefect UI.

Using the pygeoapi-prefect CLI command:

```shell
export PYGEOAPI_CONFIG=example-config.yml
export PYGEOAPI_OPENAPI=example-openapi.yml

pygeoapi plugins prefect create-remote-storage-block \
    test-sb1 \
    s3://pygeoapi-test \
    http://localhost:9000 \
    tester \
    12345678
```

Using the Prefect UI you would create a block of type _Remote File System_:

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


## Implement process code and configure pygeoapi

For this example we are using the example flow that is shipped with pygeoapi-prefect.
Use the following configuration:

```yaml
# pygeoapi configuration file: example-config.yml

resources:
  simple-flow:
    type: process
    processor:
      name: pygeoapi_prefect.examples.simple_prefect.SimpleFlowProcessor
      prefect:
        result_storage: remote-file-system/test-sb1-results
        deployment:
          name: minio
          queue: pygeoapi
          storage_block: remote-file-system/test-sb1
          storage_sub_path: simple-flow-flow
```


## Deploy process

After having created the block in prefect, we can now deploy our pygeoapi process:

```shell
export PYGEOAPI_CONFIG=example-config.yml

poetry run pygeoapi plugins prefect deploy-process hi-prefect-world
```

This results in prefect creating a deployment named `hi-prefect-world/minio`, and since we are specifying a storage
block, prefect also uploads the flow code onto the storage (which is the minIO bucket created previously).

You can verify this step by:

- Checking the presence of a `hi-prefect-world-flow` entry inside the previously created minIO bucket. By running
  the `deploy-process` command you instructed prefect to upload the flow code to the minIO storage.
- Checking the existence of a `hi-prefect-world/minio` deployment, as reported in the prefect UI


## 3. Execute process via pygeoapi

```shell
http -v localhost:5000/processes/hi-prefect-world/execution inputs:='{"name": "Frankie Four-fingers"}'
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
