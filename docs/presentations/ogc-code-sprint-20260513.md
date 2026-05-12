# 2026 OGC Builder days code sprint demo

Welcome to the pygeoapi-prefect demo tutorial, prepared for the [2026 OGC Builder days code sprint]. This is a short
presentation of pygeoapi-prefect that showcases how it may be used as a replacement to the builtin process/job managers
in pygeoapi.

This is a 30 minute hands-on demo with detailed instructions so that you can follow along on your own.

In this session we will be setting up a local instance of pygeoapi with the default process/job manager and try
out some sample web requests. These will demonstrate basic OGC API - Processes support, as available in pygeoapi.

Then we will move on to setting up pygeoapi with the pygeoapi-prefect manager and show how it handles execution of
processes.

!!! info "Pre-requisites"

    This was written assuming a target audience that:

    - Is familiar with Python;
    - Has heard about [pygeoapi] before but is not necessarily familiarized with it;
    - Has heard about the [OGC API - Processes] standard but is not necessarily super familiarized with it.


## Overview

### OGC API - Processes (OAProc)

OGC API - Processes is a geospatial standard that specifies how servers can expose computational tasks
via a web API. These can then be executed on demand by web clients. A very brief overview:

- Servers expose **processes**
- A process describes a computation that the server is able to run
- Processes may take **inputs** and generate **outputs**
- A client requests **execution** of a process, providing relevant inputs
- Execution can be **synchronous** or **asynchronous**
- When execution is requested, the server eventually spawns a **job**
- Upon successful completion, job outputs are made available to the client

Read all about it at the official [OGC API - Processes] documentation website.


### pygeoapi

[pygeoapi] is a Python-based web application that implements support for a growing number of OGC API standards. It
is an open source project, MIT licensed, with a friendly community. It is easily extendable through plugins
pygeoapi is officially certified by the OGC as compliant with OGC API - Processes.


## pygeoapi-prefect

pygeoapi-prefect is a **plugin for pygeoapi** that implements a custom **process/job manager**. It defers most
operations to [Prefect], effectively acting as a bridge between pygeoapi and Prefect.

It is an open source project, funded and steered by [Geobeyond] and is MIT licensed. It is implemented in Python
and distributed via the [Python Package Index], making it trivial to install.

[Python Package Index]: https://pypi.org/project/pygeoapi-prefect/

pygeoapi-prefect aims to augment pygeoapi's support for OAProc with a number of features to improve its robustness
and reliability, including:

- Ability to horizontally scale both compute and storage
- Provide isolated and customizable computation environments
- Maintain stable execution conditions by means of controlling the number of concurrent executing processes
- Deal with transient errors by specifying failure and retry logic
- Enjoy improved runtime and historical monitoring with a rich UI


### Integration levels

pygeoapi-prefect has three levels of integration with pygeoapi, as summarized below:

| Level | Description | Pros and Cons |
| :---: | ----------- | ------------- |
| 1 | - Swap out builtin manager<br>- Use `sync` execution mode | :green_circle: Use regular pygeoapi processes<br>:green_circle: Prefect UI for monitoring<br>:green_circle: Prefect result storage<br>:orange_circle: Slower than builtin manager's `sync` responses<br>:orange_circle: Runs in the same process as pygeoapi<br>:orange_circle: Uses same environment as pygeoapi |
| 2 | - Swap out builtin manager<br>- Use `async` execution mode | :green_circle: Use regular pygeoapi processes<br>:green_circle: Prefect UI for monitoring<br>:green_circle: Prefect result storage<br>:green_circle: Control concurrency<br>:orange_circle: Runs on the same node as pygeoapi<br>:orange_circle: Uses similar environment as pygeoapi |
| 3 | - Swap out builtin manager<br>- Use `async` execution mode<br>- Self deploy Prefect flows | :green_circle: Prefect UI for monitoring<br>:green_circle: Prefect result storage<br>:green_circle: Control concurrency<br>:green_circle: Use multiple workers<br>:green_circle: Run anywhere there is Prefect support (docker, k8s, etc)<br>:green_circle: Customize execution environment<br>:orange_circle: Very flexible, but can become complex  to set up|


#### Level-1

Swap out the default pygeoapi manager and then run sync vanilla processes via Prefect.

This simply runs the normal pygeoapi vanilla processes in the same process as the pygeoapi web application
server. Executed jobs are registered in the Prefect DB and can be inspected via the Prefect UI (and API).

This mode is already a nice improvement over the builtin pygeoapi manager(s):

- Execution results are stored and managed by Prefect, which allows using its [storage framework]. This allows,
  for example, storing results in cloud storage instead of the local filesystem in a transparent way
- Execution monitoring via Prefect UI provides a rich interface for both real-time and historical purposes

Note that these benefits also come at a cost, as executing processes in `sync` mode via the pygeoapi-prefect
manager is slower than using any of the builtin pygeoapi managers.


#### Level-2

Run async vanilla processes. This mode uses a dedicated Prefect worker to run pygeoapi vanilla
processes in a different process than the main pygeoapi web application. The Prefect worker is started by
running a custom CLI command, `pygeoapi plugins prefect deploy-static`.

In addition to using Prefect for result storage and enabling usage of the Prefect UI for monitoring, this mode
runs jobs outside the main web request/response cycle and allows some control over the overall stability of the
node by leveraging Prefect's concurrency levels. It becomes possible to ensure that only a predefined number
of jobs can be running at the same time, while any others will be queued.


#### Level-3

Run previously deployed Prefect flows. This mode unlocks the full breadth of Prefect features. It
consists of running Prefect flows that have been previously deployed to any of the supported Prefect infrastructure
setups (running jobs inside ephemeral docker containers, using k8s, etc.). You can achieve virtually infinite scaling
of both compute and storage, employ multiple types of concurrency limits, etc.

In this demo, we are keeping to Level-2 integration. Check the rest of the pygeoapi-prefect documentation for more
information on more advanced features.

[storage framework]: https://docs.prefect.io/v3/advanced/results
[Geobeyond]: https://www.geobeyond.it/
[Prefect]: https://www.prefect.io/
[pygeoapi]: https://pygeoapi.io/
[OGC API - Processes]: https://ogcapi.ogc.org/processes/

[2026 OGC Builder days code sprint]: https://github.com/opengeospatial/developer-events/wiki/May-2026-Builder-Days-Code-Sprint#microsoft-


### Further work

In its present form, pygeoapi-prefect is a robust alternative to the builtin pygeoapi job/process managers and
is suitable for production deployments. We will continue to improve it

-   Improve job listing feedback

-   Work on docs:
    -   Improve the user guide
    -   Add more examples

-   Implement missing OAProc functionalities

    - `dismiss` - Ability to cancel on-going jobs
    - `subscriber` - Ability to callback an HTTP endpoint when results are ready

-   Keep an eye out for upcoming OAProc Parts and implement them


## Practical session


### 0 - Setup

Let's start by installing and preparing our set up.

-   Create a venv and activate it
-   Install pygeoapi master from github (because the fix for [issue #2311] has not been released yet)
-   Install pygeoapi-prefect
-   Get a sample pygeoapi configuration file that we can copy, tweak and use

[issue #2311]: https://github.com/geopython/pygeoapi/issues/2311


```shell
mkdir pygeoapi-prefect-demo
cd pygeoapi-prefect-demo

python -m venv .venv
source .venv/bin/activate

pip install git+https://github.com/geopython/pygeoapi@master
pip install pygeoapi-prefect

# get a sample pygeoapi configuration file to tweak
curl -so sample-pygeoapi-config.yml \
  https://raw.githubusercontent.com/geopython/pygeoapi/refs/heads/master/pygeoapi-config.yml
```


### 1 - Run pygeoapi with the default process manager

Let's start by running pygeoapi with its default process/job manager

Copy the pygeoapi configuration file

```shell
cp sample-pygeoapi-config.yml demo-pygeoapi-config-0-default-manager.yml
```

Tweak it:

-   Enable the default manager (TinyDB) by uncommenting the existing lines in the `server.manager` section
-   For simplicity, keep only resources of type `process`


??? tip "Contents of `demo-pygeoapi-config-0-default-manager.yml`"

    We are starting out with this configuration:

    ```yaml linenums="1"
    server:
      bind: {host: "0.0.0.0", port: 5000}
      url: "http://localhost:5000"
      mimetype: "application/json; charset=UTF-8"
      encoding: "utf-8"
      gzip: false
      languages: ["en-US"]
      pretty_print: true
      limits: {default_items: 20, max_items: 50}
      map:
        url: "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution: '&copy; <a href="https://openstreetmap.org/copyright">OpenStreetMap contributors</a>'
      admin: false
      manager:
        name: "TinyDB"
        connection: "/tmp/pygeoapi-process-manager.db"
        output_dir: "/tmp/"
    logging: {level: "ERROR"}
    metadata:
      identification:
        title: {en: "pygeoapi default instance"}
        description: {en: "pygeoapi provides an API to geospatial data"}
        keywords: {en: ["geospatial"]}
        keywords_type: "theme"
        terms_of_service: "https://creativecommons.org/licenses/by/4.0/"
        url: "https://example.org"
      license: {name: "CC-BY 4.0 license", url: "https://creativecommons.org/licenses/by/4.0/"}
      provider: {name: "Organization Name", url: "https://pygeoapi.io"}
      contact: {
        name: "Lastname, Firstname", position: "Position Title",
        address: "Mailing Address", city: "City",
        stateorprovince: "Administrative Area", postalcode: "Zip or Postal Code",
        country: "Country", phone: "+xx-xxx-xxx-xxxx",
        fax: "+xx-xxx-xxx-xxxx", email: "you@example.org",
        url: "Contact URL", hours: "Mo-Fr 08:00-17:00", role: "pointOfContact",
        instructions: "During hours of service. Off on weekends.",
      }

    resources:
      hello-world:
        type: "process"
        processor:
          name: "HelloWorld"
    ```

Generate pygeoapi's OpenAPI document by using the pygeoapi CLI:

```shell
# ensure venv is activated before running this

pygeoapi openapi generate \
    demo-pygeoapi-config-0-default-manager.yml \
    -of demo-pygeoapi-openapi.yml
```

Start the pygeoapi server:

```shell
# ensure venv is activated before running this

PYGEOAPI_CONFIG=demo-pygeoapi-config-0-default-manager.yml \
  PYGEOAPI_OPENAPI=demo-pygeoapi-openapi.yml \
  pygeoapi serve
```


### 2 - Check out pygeoapi's OGC API - Processes implementation

Let's try out some API requests with [cURL], to get acquainted with OAProc.


[cURL]: https://curl.se/


#### Landing page

Note how `/processes` and `/jobs` path operations are advertised in `links`

```shell
curl -s http://localhost:5000 | jq '.'
```


#### Process listing

Note existence of the `hello-world` process


```shell
curl -s http://localhost:5000/processes | jq '.'
```


#### Process details

```shell
curl -s http://localhost:5000/processes/hello-world | jq '.'
```


#### Process execution in sync mode

-   Response is returned inline
-   HTTP Status code is `200 OK`


```shell
curl -sS \
  -X POST http://localhost:5000/processes/hello-world/execution \
  -H "Content-Type: application/json" \
  -d '{"inputs": {"name": "Joe"}}' \
  -w "\n"
```


#### Process execution in async mode

-   Note how the request sends the `Prefer: respond-async` request header
-   Response is not returned, just a job id and initial status
-   HTTP Status code is `201 Accepted`
-   HTTP Response header `Location` contains URL for job details

```shell
curl -sSi \
  -X POST http://localhost:5000/processes/hello-world/execution \
  -H "Content-Type: application/json" \
  -H "Prefer: respond-async" \
  -d '{"inputs": {"name": "Joe"}}' \
  -w "\n"
```


#### Job details

```shell
curl -s http://localhost:5000/jobs/{job-id}
```

Response contains:
-   Job status
-   Links for getting results


#### Job results

```shell
curl -s -H "Accept: application/json" \
  http://localhost:5000/jobs/{job-id}/results
```


### 3 - Setup for pygeoapi-prefect

We need:

-   Prefect server up and running
-   Tweak pygeoapi's config file to enable pygeoapi-prefect manager
-   Prefect worker up and running (for handling async requests)


#### 3.1 - Start Prefect server locally

Set some env variables and start a local Prefect server

```shell
# ensure venv is activated before running this

PREFECT_API_URL=http://127.0.0.1:4200/api \
  PREFECT_RESULTS_PERSIST_BY_DEFAULT=true \
  prefect server start
```

You can now access the Prefect UI at <http://localhost:4200>.


#### 3.2 - Tweak pygeoapi config

Stop the running pygeoapi server and let's now modify the configuration, enabling pygeoapi-prefect manager.
Copy the configuration file into a new `demo-pygeoapi-config-1-prefect-manager.yml` file and make these changes:

```shell
cp demo-pygeoapi-config-0-default-manager.yml demo-pygeoapi-config-1-prefect-manager.yml
```

```diff linenums="14"
- manager:
-   name: "TinyDB"
-   connection: "/tmp/pygeoapi-process-manager.db"
-   output_dir: "/tmp/"
+ manager:
+   name: "pygeoapi_prefect.PrefectManager"
+   enable_sync_job_execution: true
```

In other words, we are replacing the builtin `TinyDB` manager with `pygeoapi_prefect.PrefectManager`. We also
configure the new manager with `enable_sync_job_execution: true`. In pygeoapi-prefect, sync execution is disabled
by default.

??? tip "Full contents of `demo-pygeoapi-config-1-prefect-manager.yml`"

    We will now be using this configuration:

    ```yaml linenums="1"
    server:
      bind: {host: "0.0.0.0", port: 5000}
      url: "http://localhost:5000"
      mimetype: "application/json; charset=UTF-8"
      encoding: "utf-8"
      gzip: false
      languages: ["en-US"]
      pretty_print: true
      limits: {default_items: 20, max_items: 50}
      map:
        url: "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution: '&copy; <a href="https://openstreetmap.org/copyright">OpenStreetMap contributors</a>'
      admin: false
      manager:
        name: "pygeoapi_prefect.PrefectManager"
        enable_sync_job_execution: true
    logging: {level: "ERROR"}
    metadata:
      identification:
        title: {en: "pygeoapi default instance"}
        description: {en: "pygeoapi provides an API to geospatial data"}
        keywords: {en: ["geospatial"]}
        keywords_type: "theme"
        terms_of_service: "https://creativecommons.org/licenses/by/4.0/"
        url: "https://example.org"
      license: {name: "CC-BY 4.0 license", url: "https://creativecommons.org/licenses/by/4.0/"}
      provider: {name: "Organization Name", url: "https://pygeoapi.io"}
      contact: {
        name: "Lastname, Firstname", position: "Position Title",
        address: "Mailing Address", city: "City",
        stateorprovince: "Administrative Area", postalcode: "Zip or Postal Code",
        country: "Country", phone: "+xx-xxx-xxx-xxxx",
        fax: "+xx-xxx-xxx-xxxx", email: "you@example.org",
        url: "Contact URL", hours: "Mo-Fr 08:00-17:00", role: "pointOfContact",
        instructions: "During hours of service. Off on weekends.",
      }

    resources:
      hello-world:
        type: "process"
        processor:
            name: "HelloWorld"
    ```


Restart pygeoapi

```shell
# ensure venv is activated before running this

PYGEOAPI_CONFIG=demo-pygeoapi-config-1-prefect-manager.yml \
  PYGEOAPI_OPENAPI=demo-pygeoapi-openapi.yml \
  pygeoapi serve
```

Note how existing processes get validated upon initialization - this is a JSON Schema validation of
their own description.


#### 3.3 - Start a local Prefect worker

In order to be able to respond to async execution requests, a Prefect worker needs to be started and
existing processes must be deployed. For vanilla pygeoapi processes, this can be done by running a
custom CLI command:

```shell
# ensure venv is activated before running this

PYGEOAPI_CONFIG=demo-pygeoapi-config-1-prefect-manager.yml \
  PREFECT_API_URL=http://127.0.0.1:4200/api \
  pygeoapi plugins prefect deploy-local --concurrency-limit 5
```

This command performs both:

- Register each pygeoapi process as a Prefect deployment so that it becomes known to Prefect;
- Starts a worker process that is able to execute pygeoapi processes on demand. The worker is able to handle five
  concurrent executions, which means that if there is ever a larger number of jobs to handle simultaneously, Prefect
  will automatically enqueue them and process each according to the limits

Browse the Prefect UI and discover the newly registered deployment of flows.


### 4 - Use pygeoapi-prefect

With the configuration done, pygeoapi will now defer execution of jobs to Prefect. Let's now make some test requests.


#### Process execution in sync mode

pygeoapi-prefect is optimized for running in `async` mode, as that is how it is able to control job concurrency.
However, it can also execute in `sync` mode, provided that this is enabled in the configuration by setting
`manager.enable_sync_job_execution: true`.

Note that the pygeoapi-prefect manager honors what is specified in [section 7.11.2.3 of the OGC API - Processes standard],
so if sync mode is enabled (like we did when we created the pygeoapi configuration file), then it becomes the default
mode.

[section 7.11.2.3 of the OGC API - Processes standard]: https://docs.ogc.org/is/18-062r2/18-062r2.html#sc_execution_mode

Try out the following request:

```shell
curl -sS \
  -X POST http://localhost:5000/processes/hello-world/execution \
  -H "Content-Type: application/json" \
  -d '{"inputs": {"name": "Joe"}}' \
  -w "\n"
```

Note that:

-   The generated result is the same as with the vanilla manager - we are running the same processor code
-   Execution details are now tracked in the Prefect UI - look for it in the _Runs_ section of the UI
-   Sync execution mode is now _slower_ than before, because it is coordinated by Prefect.


!!! warning

    We advise keeping sync mode turned off and using async execution. This allows Prefect to enforce concurrency
    limits and keep load on the pygeoapi server under control, even in the case of high traffic.


#### Process execution in async mode

Async mode can be requested by sending the `Prefer: respond-async` HTTP request header. Execution is
scheduled by Prefect and coordinated by the worker we started earlier. Each job is run on a separate OS process
and results are communicated back to Prefect.

The pygeoapi-prefect manager is then able to query the Prefect DB whenever it needs to know about execution status
and retrieve results.

```shell
curl -sSi \
  -X POST http://localhost:5000/processes/hello-world/execution \
  -H "Content-Type: application/json" \
  -H "Prefer: respond-async" \
  -d '{"inputs": {"name": "Joe"}}' \
  -w "\n"
```


#### Job details

```shell
curl -s http://localhost:5000/jobs/{job-id}
```

Response contains:
-   Job status
-   Links for getting results


#### Job results

```shell
curl -s -H "Accept: application/json" \
  http://localhost:5000/jobs/{job-id}/results
```



#### Controlling server load

We can test out Prefect's concurreny handling by making many simultaneous requests and checking their execution
status in the Prefect UI.

For example, let's make 50 simultaneous requests:

```shell
seq 50 | xargs -P 0 -I{} sh -c '
    name=$(shuf -n 1 /usr/share/dict/words)
    payload=$(jq -nc --arg n "$name" "{inputs: {name: \$n}}")
    curl -sS -o /dev/null -w "%{http_code}\n" \
        -X POST "http://localhost:5000/processes/hello-world/execution" \
        -H "Content-Type: application/json" -H "Prefer: respond-async" \
        -d "$payload"
'
```


??? tip "Command breakdown"

    The above command contains a lot of instructions. Let's make some sense of it:

    - `seq 50` generates numbers from 1 to 50, one per line - this is just a way to specify the total number of
      requests that we want to perform
    - `shuf -n1 /usr/share/dict/words` gets a random word from the
      [words file](https://en.wikipedia.org/wiki/Words_(Unix)) so that we can add some variability to our cURL
      request payloads
    - `xargs -P0 -I{} -c` means we are invoking the [xargs](https://www.man7.org/linux/man-pages/man1/xargs.1.html)
      command to run cURL once for each item passed in via stdin, but don't pass the actual item to cURL, _i.e._
      _"run the next command 50 times, in parallel"_
    - `jq ...` means we use the [jq](https://jqlang.org/) command to build the HTTP request JSON payload to send.
      This is just a way to generate valid JSON data from the random word that was picked
    - `curl ...` is the actual command that is being run multiple times


After running the above command, head over to the Prefect UI and check how despite being passed a large number of
execution requests, the server only executes five of them at a time while the others are awaiting their turn. Eventually
all requests are processed.


## Q & A

Thanks for attending! :rainbow:

If further interested, checkout the rest of the docs and feel free to reach out via discord
or email
