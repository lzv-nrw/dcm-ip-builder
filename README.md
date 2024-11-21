# Digital Curation Manager - IP Builder

The 'DCM IP Builder'-API provides functionality to convert Intellectual Entities (IEs) into Information Packages (IPs) and validate IP-format (metadata and payload structure).
This repository contains the corresponding Flask app definition.
For the associated OpenAPI-document, please refer to the sibling package [`dcm-ip-builder-api`](https://github.com/lzv-nrw/dcm-ip-builder-api).

The contents of this repository are part of the [`Digital Curation Manager`](https://github.com/lzv-nrw/digital-curation-manager).

## Local install
Make sure to include the extra-index-url `https://zivgitlab.uni-muenster.de/api/v4/projects/9020/packages/pypi/simple` in your [pip-configuration](https://pip.pypa.io/en/stable/cli/pip_install/#finding-packages) to enable an automated install of all dependencies.
Using a virtual environment is recommended.

1. Install with
   ```
   pip install .
   ```
1. Configure service environment to fit your needs ([see here](#environmentconfiguration)).
1. Run app as
   ```
   flask run --port=8080
   ```
1. To manually use the API, either run command line tools like `curl` as, e.g.,
   ```
   curl -X 'POST' \
     'http://localhost:8080/validate/ip' \
     -H 'accept: application/json' \
     -H 'Content-Type: application/json' \
     -d '{
     "validation": {
       "target": {
         "path": "jobs/abcde-12345-fghijk-67890"
       },
       "modules": [
         "bagit_profile",
         "payload_structure",
         "payload_integrity",
         "file_format"
       ],
       "args": {
         "bagit_profile": {
           "baginfoTagCaseSensitive": true,
           "profileUrl": "bagit_profiles/dcm_bagit_profile_v1.0.0.json"
         },
         "payload_structure": {
           "profileUrl": "bagit_profiles/dcm_bagit_profile_v1.0.0.json"
         }
       }
     }
   }'
   ```
   or run a gui-application, like Swagger UI, based on the OpenAPI-document provided in the sibling package [`dcm-ip-builder-api`](https://github.com/lzv-nrw/dcm-ip-builder-api).

### Extra dependencies

#### Metadata-Mapping
The IP Builder app-package defines an optional dependency for the [`dcm-metadata-mapper`](https://github.com/lzv-nrw/dcm-metadata-mapper) which can significantly simplify the definition of mapping scripts (as required by the `POST-/build` endpoint).
This extra can be installed with
```
pip install ".[mapping]"
```

## Run with docker compose
Simply run
```
docker compose up
```
By default, the app listens on port 8080.
The docker volume `file_storage` is automatically created and data will be written in `/file_storage`.
To rebuild an already existing image, run `docker compose build`.

Additionally, a Swagger UI is hosted at
```
http://localhost/docs
```

Afterwards, stop the process and enter `docker compose down`.

## Tests
Install additional dev-dependencies with
```
pip install -r dev-requirements.txt
```
Run unit-tests with
```
pytest -v -s
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

as listed [here](https://github.com/lzv-nrw/dcm-common#app-configuration).

# Contributors
* Sven Haubold
* Orestis Kazasidis
* Stephan Lenartz
* Kayhan Ogan
* Michael Rahier
* Steffen Richters-Finger
* Malte Windrath
* Roman Kudinov