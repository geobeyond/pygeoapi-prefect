# Execute process

The following are example requests that can be made to a pygeoapi server that
uses pygeoapi-prefect

## Sync execution


### sync execution without deployment

```shell
http localhost:5000/processes/simple-flow/execution \
    inputs:='{"name": "John Doe"}'
```


### sync execution with deployment (warn about not using a reloader web server)

```shell
http localhost:5000/processes/simple-flow/execution \
    inputs:='{"name": "John Doe"}'
```


## async execution

pygeoapi implements the OGC API Processes standard, which mandates that asynchronous execution
be requested by adding the `Prefer:respond-async` HTTP header in execution requests.

### async execution without deployment (currently not supported)


### async execution with deployment

```shell
http localhost:5000/processes/simple-flow/execution \
    Prefer:respond-async \
    inputs:='{"name": "John Doe"}' \
```

### async execution with deployment and using a response of type `document`

```shell
http localhost:5000/processes/simple-flow/execution \
    Prefer:respond-async \
    response=document \
    inputs:='{"name": "John Doe"}'
```

### async execution with deployment and using a response of type `document` with result being requested by reference

```shell
http localhost:5000/processes/simple-flow/execution \
    Prefer:respond-async \
    response=document \
    inputs:='{"name": "John Doe"}'
    outputs:='{"result": {"transmissionMode": "reference"}}'
```


### Retrieve execution results

- with a storage block
- without it
