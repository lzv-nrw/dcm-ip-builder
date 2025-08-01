# Changelog

## [6.1.0] - 2025-07-30

### Changed

- adapted the payload-structure validation-plugin to mark any IP without payload as invalid
- added support for building an IP from an IE without payload

## [6.0.0] - 2025-07-25

### Changed

- **Breaking:** implemented changes for API v5

### Added

- added validation-plugin for the `significant_properties.xml`
- added identifiers to `JobData` after successful validation and if available in `bag-info.txt`-metadata
- added build-request specific validation option
- added `GenericStringPlugin` and `XSLTMappingPlugin`

### Removed

- dropped support for `AppConfig.DO_VALIDATION`

### Fixed

- fixed initialization of ScalableOrchestrator with ORCHESTRATION_PROCESSES
- fixed potential deadlocks when using `bagit_profile.Profile.get_profile`
- fixed not properly cleaning up temporary data while building bag (if a relative mount point is used)

## [5.0.0] - 2025-02-14

### Changed

- switched to non root-user in Dockerfile
- migrated to API v4

### Added

- added support for dynamically loaded mapping-plugins
- added mapping-plugin system and utilities
- added payload-structure validation-plugin
- added BagIt Profile validation-plugin based on the `bagit_profile` library
- added bag builder plugin based on `bagit` library

### Removed

- removed docker compose file
- removed `dcm-object-validator` dependency
- removed `dcm-bag-builder` dependency

## [4.0.1] - 2024-11-21

### Changed

- updated package metadata, Dockerfiles, and README

## [4.0.0] - 2024-10-16

### Changed

- migrated to `dcm-s11n` v2 (`009c0803`)
- **Breaking:** implemented changes of API v3 (`33822c59`, `1726b51d`)
- migrated to `dcm-common` (scalable orchestration and related components; latest `DataModel`) (`33822c59`)

## [3.0.1] - 2024-07-25

### Fixed

- added missing and improved existing log-messages during build and validation (`68a18e91`)

## [3.0.0] - 2024-07-24

### Changed

- improved report.progress.verbose and log messages (`72d779d8`, `65d766aa`, `bf466184`)
- **Breaking:** updated to API v2 (`be5b3cb3`, `24ec52bf`)

### Fixed

- fixed bad values for `data.valid` in intermediate reports (`24ec52bf`)
- fixed generation of fallback-report on external timeout (`80720c36`)

## [2.0.1] - 2024-04-30

### Fixed

- fixed erroneous handling of `target.path` (`ff94376a`)

## [2.0.0] - 2024-04-25

### Changed

- switched to importing validation logic from object validator (`8540a008`)
- switched to new sdk for object validator api v2 (`8540a008`)
- **Breaking:** implemented changed ip builder api v1 (`8540a008`)
- updated version for `lzvnrw_supplements.orchestration` (`8540a008`)
- **Breaking:** shorten name of app-starter `app.py` (`1e6e20b9`)
- **Breaking:** shorten name of config-class (`edd03cca`, `cf4d1a06`)
- set the default value of `ignore_baginfo_tag_case` in the configuration based on the API document (`d7251a72`)
- changed request.host to request.host_url for the host-property of a report (`14964041`)
- updated input-handling based on data-plumber-http (`196e7f74`)

### Added

- added extras-dependency for `Flask-CORS` and `dcm-metadata-mapper` (`b17319f9`)
- introduce the usage of dc.xml (`d3a2c5a3`)

### Fixed

- fixed loading of default profiles (`9c04946d`)
- fixed the XPath syntax for lxml (`89646928`)

## [1.0.1] - 2024-01-26

### Fixed

- fixed issue with the timeout-detection when forwarding validation to an Object Validator (`3b80d6b7`)

## [1.0.0] - 2024-01-26

### Changed

- **Breaking:** switch to supported Object-Validator-API version 1.0.0 (`b7e8764c`)
- update implemented API-version to 0.3.0 (`56e6d84d`)
- change generation method of IP folder names (`d0ac5096`, `495598db`)
- make use of GitLab package registry in Dockerfiles (`c77e9c73`)
- **Breaking:** the configuration property of the `build` endpoint has to be a class object (`af877e42`)
- only return the IP path if the build process was successful (`34e8d505`, `5df518ae`)

### Added

- **Breaking:** add thorough input validation (`1048933d`)
- the identify-response can include a version string for the dcm-metadata-mapper (`64a2890a`)
- add configuration attributes for the manifest and tag-manifest algorithms for the build process (`6fb3e113`,`f10f62f3`)

### Fixed

- improved and updated README usage-instructions for changed behavior (`17b081d1`) 
- fix only give Object-Validator backend info in /identify if available (`7606b26a`)
- implement forwarding of validation requests to Object-Validator-service (`94db8d61`)
- (PATCH) fix issue, where on error a duplicate of the bagit_profile-report is copied into the validation-report (`6ffa40fb`)

## [0.1.0] - 2024-01-19

### Changed

- initial release of dcm-ip-builder
