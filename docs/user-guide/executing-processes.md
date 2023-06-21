# Execute process

- Examples:
    - sync execution without deployment

      ```shell
      http localhost:5000/processes/simple-flow/execution \
          inputs:='{"name": "John Doe"}'
      ```
    - async execution without deployment (currently not supported)

    - sync execution with deployment (warn about not using a reloader web server)

      ```shell
      http localhost:5000/processes/simple-flow/execution \
          inputs:='{"name": "John Doe"}'
      ```

    - async execution with deployment

      ```shell
      http localhost:5000/processes/simple-flow/execution \
          Prefer:respond-async \
          inputs:='{"name": "John Doe"}' \
      ```

    - async execution with deployment and using a response of type `document`

      ```shell
      http localhost:5000/processes/simple-flow/execution \
          Prefer:respond-async \
          response=document \
          inputs:='{"name": "John Doe"}'
      ```

    - async execution with deployment and using a response of type `document` with result being requested by reference

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
