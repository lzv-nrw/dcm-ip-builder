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
     'http://localhost:8080/validate' \
     -H 'accept: application/json' \
     -H 'Content-Type: application/json' \
     -d '{
     "validation": {
       "target": {
         "path": "jobs/abcde-12345-fghijk-67890"
       }
     }
   }'
   ```
   or run a gui-application, like Swagger UI, based on the OpenAPI-document provided in the sibling package [`dcm-ip-builder-api`](https://github.com/lzv-nrw/dcm-ip-builder-api).

### Extra dependencies

#### Lax Metadata-Mapping
The IP Builder app-package defines an optional dependency for the [`dill`](https://github.com/uqfoundation/dill)-library which is used by the `generic-mapping-plugin-b64`.
For its use, refer to the description [here](#metadata-mapping).
Beware of the safety concerns when executing unknown code (see also [here](#additional-plugins)).
This extra can be installed with
```
pip install ".[lax-mapping]"
```

## List of plugins
Part of this implementation is a plugin-system for the mapping of metadata from source to IP.
It is based on the general-purpose plugin-system implemented in `dcm-common`.

### Metadata mapping
The natively provided metadata mapping-plugins
* `xslt-plugin`,
* `generic-mapper-plugin-string`,
* `generic-mapper-plugin-base64`, and
* `generic-mapper-plugin-url`

allow to perform metadata mapping based on either
* an xsl-transformation (version 1.0) as string (see [example](#XSLT)),
* the contents of a python module containing a class named `ExternalMapper` that implements the interface `dcm_ip_builder.plugins.mapping.GenericMapper` as string,
* a `dill`-serialized and base64-encoded version of that class,  or
* a url referencing a python-module containing that class

when building IPs.

This way, the mapping process can be freely customized.
Note that due to the security implications, it is recommended to instead use [external plugins](#additional-plugins) to provide a set of trusted plugins.

#### XSLT
The output document of the `xslt` should be a well-formed xml string whose root element is `metadata`.
The metadata should be grouped in elements named `field` with the key as attribute and the value as text.
No nesting is allowed. Any namespace prefixes in the output are ignored.

This is an example implementation of a minimal `xslt` that is compatible with the `xslt-plugin`
```xml
<xsl:stylesheet xmlns:oai="http://www.openarchives.org/OAI/2.0/" 
                xmlns:dc="http://purl.org/dc/elements/1.1/"
                xmlns:oai_dc="http://www.openarchives.org/OAI/2.0/oai_dc/"
                xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
                exclude-result-prefixes="oai oai_dc dc" version="1.0">
    <xsl:output method="xml" indent="yes" encoding="UTF-8"/>
    <xsl:template match="/">
        <metadata>
            <xsl:apply-templates select="//oai_dc:dc"/>
            <field>
                <xsl:attribute name="key">
                    <xsl:text>Source-Organization</xsl:text>
                </xsl:attribute>
                <xsl:text>https://d-nb.info/gnd/0</xsl:text>
            </field>
        </metadata>
    </xsl:template>
    <xsl:template match="//oai_dc:dc">
        <xsl:for-each select="//dc:rights">
            <field>
                <xsl:attribute name="key">
                    <xsl:text>DC-Rights</xsl:text>
                </xsl:attribute>
                <xsl:value-of select="."/>
            </field>
        </xsl:for-each>
    </xsl:template>
</xsl:stylesheet>
```
It correctly processes dc-rights information from an input source-file and adds the source organization.

#### Python
In order to enable the `generic`-type plugins, set the `ALLOW_GENERIC_MAPPING`-variable accordingly.
Also note that by default the `dill`-based (de-)serialization does not serialize dependencies.
Consequently, potential additional dependencies of `ExternalMapper`s have to be installed manually in the IP Builder's environment before that mapper becomes usable.

This is an example implementation of a minimal `GenericMapper` that is compatible with this approach
```python
from pathlib import Path
from dcm_ip_builder.plugins.mapping import GenericMapper, util

class ExternalMapper(GenericMapper):
    """Mapper for OAI-protocol to BagIt-metadata."""

    NAMESPACES = {
        "": "http://www.openarchives.org/OAI/2.0/",
        "oai_dc": "http://www.openarchives.org/OAI/2.0/oai_dc/",
        "dc": "http://purl.org/dc/elements/1.1/",
    }
    RULE = util.XMLXPathMappingRule(
        "./GetRecord/record/metadata/oai_dc:dc/dc:title",
        "DC-Title",
        ns=NAMESPACES,
    )

    def get_metadata(self, path, /, **kwargs):
        tree = util.load_xml_tree_from_file(Path(path))
        title = self.RULE.map(tree)
        if not title:
            raise ValueError("Source metadata missing title-information.")
        return {self.RULE.dst: title}
```
It correctly processes dc-title information from an input source-file and raises an error if the title is missing.

In order to convert this into a valid base64-string, perform the following steps
* install the python packages `dill` and `dcm-ip-builder` (and any other dependency required by the mapper; note that just like with external plugins, all plugin-dependencies need to be available in the environment in which the IP Builder is executed)
* run the python script `convert_mapper_to_base64.py` on your script file

Furthermore, the plugin `demo` can be loaded by setting the environment variable `USE_DEMO_PLUGIN`.
It can be used to map demo-data generated by the Import Module demo-plugin.

The expected call signatures and more information for individual plugins are provided via the API at runtime (endpoint `GET-/identify`).

### Additional plugins
This service supports dynamically loaded additional plugins which implement the common plugin-interface.
In order to load additional plugins, use the environment variable `ADDITIONAL_MAPPING_PLUGINS_DIR`.
If set, the app will search for valid implementations in all modules that are in the given directory-tree.
To qualify as a plugin, the classes need to
* implement the `PluginInterface` as defined in the [`dcm-common`-package](https://github.com/lzv-nrw/dcm-common),
* be named `ExternalPlugin` (only one plugin per module), and
* define the correct context (`"mapping"`, respectively).

It is recommended to use the `MappingPlugin`-interface defined in this package as basis, e.g., like
```python
from dcm_common.plugins import Signature

from dcm_ip_builder.plugins.mapping import (
    MappingPlugin,
)


class ExternalPlugin(MappingPlugin):
    _NAME = "custom-mapping-plugin"
    _DISPLAY_NAME = "Custom-Plugin"
    _DESCRIPTION = "Custom mapping-plugin."
    _SIGNATURE = Signature(
        path=MappingPlugin.signature.properties["path"],
        ...
    )

    def _get(self, context, /, **kwargs):
        # ... custom mapping code here
        return context.result
```

All plugins are currently required to support pickling of instances via the [`dill`](https://github.com/uqfoundation/dill)-library.

## Docker
Build an image using, for example,
```
docker build -t dcm/ip-builder:dev .
```
Then run with
```
docker run --rm --name=ip-builder -p 8080:80 dcm/ip-builder:dev
```
and test by making a GET-http://localhost:8080/identify request.

For additional information, refer to the documentation [here](https://github.com/lzv-nrw/digital-curation-manager).

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
* `MANIFESTS` [DEFAULT '["sha256", "sha512"]']: list with the algorithms to be used for the manifest files when building an IP;
possible values: "md5", "sha1", "sha256" and "sha512"
* `TAG_MANIFESTS` [DEFAULT '["sha256", "sha512"]']: list with the algorithms to be used for the tag-manifest files when building an IP;
possible values: "md5", "sha1", "sha256" and "sha512"
* `ALLOW_GENERIC_MAPPING` [DEFAULT 0]: whether the generic mapping-plugins are loaded
* `ADDITIONAL_MAPPING_PLUGINS_DIR` [DEFAULT null]: directory with external mapping plugins to be loaded (see also [this explanation](#additional-plugins))
* `USE_DEMO_PLUGIN` [DEFAULT 0]: whether the demo mapping-plugin is loaded

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