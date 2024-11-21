from setuptools import setup

setup(
    version="4.0.1",
    name="dcm-ip-builder",
    description="flask app implementing the DCM IP Builder API",
    author="LZV.nrw",
    license="MIT",
    python_requires=">=3.10",
    install_requires=[
        "flask==3.*",
        "lxml==5.*",
        "requests==2.*",
        "PyYAML==6.*",
        "data-plumber-http>=1.0.0,<2",
        "dcm-common[services, db, orchestration]>=3.14.0,<4",
        "dcm-bag-builder>=2.0.0,<3.0.0",
        "dcm-s11n>=2,<3.0.0",
        "dcm-ip-builder-api>=3.1.0,<4.0.0",
        "dcm-object-validator>=4.0.0,<5.0.0",
        "dcm-object-validator-sdk>=4.1.0,<5.0.0",
    ],
    packages=[
        "dcm_ip_builder",
        "dcm_ip_builder.views",
        "dcm_ip_builder.models",
    ],
    package_data={
        "dcm_ip_builder": [
            "dcm_ip_builder/static/bagit_profile.json",
            "dcm_ip_builder/static/payload_profile.json"
        ],
    },
    include_package_data=True,
    extras_require={
        "cors": ["Flask-CORS==4"],
        "mapping": ["dcm-metadata-mapper>=0.6,<2.0"],
    },
    setuptools_git_versioning={
        "enabled": True,
        "version_file": "VERSION",
        "count_commits_from_version_file": True,
        "dev_template": "{tag}.dev{ccount}",
    },
)
