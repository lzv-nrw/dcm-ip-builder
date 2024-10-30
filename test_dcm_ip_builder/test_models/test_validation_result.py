"""ValidationResult-data model test-module."""

from dcm_ip_builder.models import ValidationResult


def test_ValidationResult_json_wlogid():
    """Test property `json` of model `ValidationResult`."""

    json = ValidationResult(logid=["id"]).json

    assert "logId" in json
    assert "id" in json["logId"]


def test_ValidationResult_json_wologid():
    """Test property `json` of model `ValidationResult`."""

    json = ValidationResult(logid=None).json

    assert "logId" not in json
