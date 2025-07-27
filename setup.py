from setuptools import setup


setup(
    version="7.0.0",
    name="dcm-ip-builder",
    description="flask app implementing the DCM IP Builder API",
    author="LZV.nrw",
    license="MIT",
    python_requires=">=3.10",
    install_requires=[
        "flask==3.*",
        "PyYAML==6.*",
        "bagit-utils>=1.1.1,<2.0.0",
        "lxml==5.*",
        "data-plumber-http>=1.0.0,<2",
        "dcm-common[services, orchestra, xml]>=4.0.0,<5",
        "dcm-ip-builder-api>=6.0.0,<7",
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
