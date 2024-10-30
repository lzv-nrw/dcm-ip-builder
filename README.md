# dcm-ip-builder

## Run with python
To test the `build` route locally, copy the test IE from the `fixtures` folder
and set the environment variable `FS_MOUNT_POINT` with
```
mkdir -p test_folder
cp -r test_dcm_ip_builder/fixtures/test-ie test_folder/test-ie
cp -r test_dcm_ip_builder/fixtures/test-bag test_folder/test-bag
export FS_MOUNT_POINT=test_folder
```

Run the 'DCM IP Builder'-app locally with
```
flask run --port=8080
```
## Run with Docker
### Container setup
Use the `compose.yml` to start the `DCM IP Builder`-Container as a service:
```
docker compose up
```
(to rebuild use `docker compose build`).

A Swagger UI is hosted at
```
http://localhost/docs
```
while (by-default) the app listens to port `8080`.

Afterwards, stop the process for example with `Ctrl`+`C` and enter `docker compose down`.

The build process requires authentication with `zivgitlab.uni-muenster.de` in order to gain access to the required python dependencies.
The Dockerfiles are configured to use the information from `~/.netrc` for this authentication (a gitlab api-token is required).

### File system setup
The currently used docker volume is set up automatically on `docker compose up`. However, in order to move data from the local file system into the container, the container also needs to mount this local file system (along with the volume). To this end, the `compose.yml` needs to be modified before startup with
```
    ...
      - file_storage:/file_storage
      - type: bind
        source: ./test_dcm_ip_builder/fixtures
        target: /local
    ports:
      ...
```
By then opening an interactive session in the container (i.e., after running the compose-script) with
```
docker exec -it <container-id> sh
```
the example bags from the test-related fixtures-directory can be copied over to the volume:
```
cp -r /local/* /file_storage/
```
(The modification to the file `compose.yml` can be reverted after copying.)

## Experiment locally
The POST-method of the `build` route can be tested with a dummy configuration with
```
curl -X 'POST' \
  'http://localhost:8080/build' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
    "build": {
      "target": {
        "path": "test-ie"
      },
      "configuration": "gASV0AMAAAAAAACMCmRpbGwuX2RpbGyUjAxfY3JlYXRlX3R5cGWUk5QoaACMCl9sb2FkX3R5cGWUk5SMBHR5cGWUhZRSlIwLQnVpbGRDb25maWeUaASMBm9iamVjdJSFlFKUhZR9lCiMCl9fbW9kdWxlX1+UjA9mYWtlX2NvbmZpZ191cmyUjAlDT05WRVJURVKUaAIoaAeMDkNvbnZlcnRlckNsYXNzlGgLhZR9lChoDmgPjAhnZXRfZGljdJRoAIwQX2NyZWF0ZV9mdW5jdGlvbpSTlChoAIwMX2NyZWF0ZV9jb2RllJOUKEMCAAGUSwJLAEsASwJLAUtDQwRkAFMAlE6FlCmMBHNlbGaUjA9zb3VyY2VfbWV0YWRhdGGUhpSMCDxzdHJpbmc+lGgUSwNDAgQBlCkpdJRSlH2UjAhfX25hbWVfX5RoD3NoFE5OdJRSlH2UfZQojA9fX2Fubm90YXRpb25zX1+UfZSMDF9fcXVhbG5hbWVfX5SMF0NvbnZlcnRlckNsYXNzLmdldF9kaWN0lHWGlGKMB19fZG9jX1+UTnV0lFKUjAhidWlsdGluc5SMB3NldGF0dHKUk5RoMGgraBGHlFIwjAZNQVBQRVKUaAIoaAeMC01hcHBlckNsYXNzlGgLhZR9lChoDmgPjAxnZXRfbWV0YWRhdGGUaBYoaBgoQwIAAZRLA0sASwBLA0sBS0NoGmgbKWgcjANrZXmUaB2HlGgfaDlLBmggKSl0lFKUfZRoJGgPc2g5Tk50lFKUfZR9lChoKX2UaCuMGE1hcHBlckNsYXNzLmdldF9tZXRhZGF0YZR1hpRiaC5OdXSUUpRoM2hIaCtoNoeUUjBoLk51dJRSlGg/KGgkaA9oLk6MC19fcGFja2FnZV9flIwAlIwKX19sb2FkZXJfX5ROjAhfX3NwZWNfX5SMEV9mcm96ZW5faW1wb3J0bGlilIwKTW9kdWxlU3BlY5STlCmBlH2UKIwEbmFtZZRoD4wGbG9hZGVylE6MBm9yaWdpbpSMEmZha2VfY29uZmlnX3VybC5weZSMDGxvYWRlcl9zdGF0ZZROjBpzdWJtb2R1bGVfc2VhcmNoX2xvY2F0aW9uc5ROjA1fc2V0X2ZpbGVhdHRylImMB19jYWNoZWSUTnVijAxfX2J1aWx0aW5zX1+UY2J1aWx0aW5zCl9fZGljdF9fCmgRaDBoNmhIaAhoS3UwaCMoaCRoD2guTmhMaE1oTk5oT2hTaF1jYnVpbHRpbnMKX19kaWN0X18KaBFoMGg2aEhoCGhLdTBoM2hLaCtoCIeUUjAu"
    }
  }'
```

Then call the GET-method of the `report` route with (replace `<token_value>`)
```
http://localhost:8080/report?token=<token_value>
```
In most cases, it is be more convenient to get this information via web-browser by simply entering the respective url
```
http://localhost:8080/report?token=<token_value>
```
When using the dummy build configuration from above, the `IP` is expected to be invalid (`valid: false` in `report`).

A valid bag can be tested with
```
curl -X 'POST' \
  'http://localhost:8080/validate/ip' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
    "validation": {
      "target": {
        "path": "test-bag"
      },
      "modules": [
        "bagit_profile"
      ]
    }
  }'
```

Finally, when running with python, delete the test directory with
```
rm -r test_folder
```

## Tests
Run `flask` test-module (after installing `dev-requirements.txt`) via
```
pytest -v -s --cov dcm_ip_builder
```

## Environment/Configuration
Service-specific environment variables are
* `BAGIT_PROFILE_URL` [DEFAULT "./dcm_ip_builder/static/bagit_profile.json"]: url to bagit profile in JSON-format
* `PAYLOAD_PROFILE_URL` [DEFAULT "./dcm_ip_builder/static/payload_profile.json"]: url to bagit payload profile in JSON-format
* `USE_OBJECT_VALIDATOR` [DEFAULT 1]: (de-)activate relay-mechanism for validation requests
* `OBJECT_VALIDATOR_HOST` [DEFAULT "http://localhost:8082"]: host address for Object Validator-service
* `OBJECT_VALIDATOR_VALIDATION_TIMEOUT` [DEFAULT 3600]: time until an object-validator validation times out in seconds

Additionally this service provides environment options for
* `BaseConfig`,
* `OrchestratedAppConfig`, and
* `FSConfig`

as listed [here](https://github.com/lzv-nrw/dcm-common/-/tree/dev?ref_type=heads#app-configuration).

# Contributors
* Sven Haubold
* Orestis Kazasidis
* Stephan Lenartz
* Kayhan Ogan
* Michael Rahier
* Steffen Richters-Finger
* Malte Windrath
