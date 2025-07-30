from setuptools import setup


setup(
    version="6.1.0",
    name="dcm-ip-builder",
    description="flask app implementing the DCM IP Builder API",
    author="LZV.nrw",
    license="MIT",
    python_requires=">=3.10",
    install_requires=[
        "flask==3.*",
        "PyYAML==6.*",
        "bagit>=1.7.0,<2.0.0",
        "bagit_profile>=1.3.1,<2.0.0",
        "lxml==5.*",
        "data-plumber-http>=1.0.0,<2",
        "dcm-common[services, db, orchestration, xml]>=3.25.0,<4",
        "dcm-ip-builder-api>=5.0.0,<6.0.0",
    ],
    packages=[
        "dcm_ip_builder",
        "dcm_ip_builder.models",
        "dcm_ip_builder.plugins",
        "dcm_ip_builder.plugins.validation",
        "dcm_ip_builder.plugins.mapping",
        "dcm_ip_builder.views",
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
        "lax-mapping": ["dill>=0.3.7,<1"],
    },
    setuptools_git_versioning={
        "enabled": True,
        "version_file": "VERSION",
        "count_commits_from_version_file": True,
        "dev_template": "{tag}.dev{ccount}",
    },
)
