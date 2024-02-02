# Using prefect deployments and storage blocks

## Configure storage for flow and results

This example shall use minIO, an S3-compatible object store, to store data.
We will configure pygeoapi to use minIO for both:

- Storing process execution outputs
- Storing the deployed flow code


Let's start by spinning up the services defined in the `docker/compose.yaml` stack file,
which are:

- prefect-server
- minio

!!! NOTE

    When running prefect from the supplied `docker/compose.yaml` docker
    Compose stack, prefect server will be running locally on port 44200, which is not
    The standard port. In this case it may be easier to create a prefect profile and use
    That:

      ```sh
      # you must have prefect installed locally
      prefect profile create pygeoapi-prefect-dev
      prefect profile use pygeoapi-prefect-dev
      prefect config set PREFECT_API_URL=http://0.0.0.0:44200
      ```

Additionally you will need to run:

-  pygeoapi server

   ```sh
   export PYGEOAPI_CONFIG=example-config.yml
   export PYGEOAPI_OPENAPI=example-openapi.yml

   pygeoapi serve
   ```

-  prefect agent

   ```sh
   prefect agent start --work-queue pygeoapi
   ```


Login to the minIO dashboard at http://127.0.0.1:9090 then go ahead and create a bucket named `pygeoapi-test`

Now you need to create a prefect storage block that references this bucket. Either use the custom
CLI command shipped by pygeoapi-prefect or create the block using prefect UI.

Using the custom CLI command:

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
It uses the following configuration:

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

- Checking the presence of a `simple-flow-flow` entry inside the previously created minIO bucket. By running
  the `deploy-process` command you instructed prefect to upload the flow code to the minIO storage.
- Checking the existence of a deployment named `minio` and that has `simple-flow` as its flow name by using
  the prefect UI


## Execute process via pygeoapi

With our deployment ready, we can now run it via several mechanisms:

- By using pygeoapi's OAProc API
- Using the prefect CLI
- Using the prefect GUI


### Executing process via pygeoapi


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
