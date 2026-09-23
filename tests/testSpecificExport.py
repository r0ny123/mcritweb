#!/usr/bin/python
"""`/data/specific_export/<type>/<id>`, behind the export buttons on sample and family rows.

The route handed `getExportData` whatever sample ids it had resolved, and an id that
resolved to none gave it an empty list. McritClient sends that as `/export/`, which is
the request for the whole corpus - so an unknown or mistyped id, or a row left on screen
after its sample was deleted, downloaded every sample the backend holds. An unknown
family was a 500 instead, and a family without samples took the same whole-corpus path.
"""

import logging
import unittest
from types import SimpleNamespace

import pytest

LOG = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)-15s %(message)s")
logging.disable(logging.CRITICAL)


@pytest.fixture
def fake_mcrit(recording_mcrit):
    def get_export_data(sample_ids):
        recording_mcrit._record("getExportData", sample_ids)
        return {"sample_entries": {str(sample_id): {} for sample_id in sample_ids}}

    recording_mcrit.getExportData = get_export_data
    return recording_mcrit


def exports(fake_mcrit):
    return [call[1][0] for call in fake_mcrit.calls if call[0] == "getExportData"]


def flashes(client):
    with client.session_transaction() as test_session:
        return [message for _category, message in test_session.get("_flashes", [])]


def test_an_unknown_sample_exports_nothing(client, as_role, fake_mcrit):
    as_role("contributor")
    fake_mcrit.getSampleById = lambda sample_id: None

    response = client.get("/data/specific_export/samples/99999")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/data/export")
    assert flashes(client) == ["Sample 99999 does not exist."]
    assert exports(fake_mcrit) == []


@pytest.mark.parametrize("samples", [None, {}], ids=["unknown family", "family without samples"])
def test_a_family_with_nothing_to_export_exports_nothing(client, as_role, fake_mcrit, samples):
    as_role("contributor")
    fake_mcrit.getSamplesByFamilyId = lambda family_id: samples

    response = client.get("/data/specific_export/family/99999")

    assert response.status_code == 302
    assert flashes(client) == ["Family 99999 does not exist or has no samples to export."]
    assert exports(fake_mcrit) == []


@pytest.mark.parametrize("kind", ["samples", "family"])
def test_an_id_that_is_not_a_number_is_not_found(client, as_role, fake_mcrit, kind):
    as_role("contributor")

    assert client.get(f"/data/specific_export/{kind}/abc").status_code == 404
    assert exports(fake_mcrit) == []


def test_a_sample_exports_that_sample(client, as_role, fake_mcrit):
    as_role("contributor")
    fake_mcrit.getSampleById = lambda sample_id: SimpleNamespace(sample_id=sample_id)

    response = client.get("/data/specific_export/samples/8")

    assert response.status_code == 200
    assert "export_samples.json" in response.headers["Content-disposition"]
    assert exports(fake_mcrit) == [[8]]


def test_a_family_exports_its_samples(client, as_role, fake_mcrit):
    as_role("contributor")
    fake_mcrit.getSamplesByFamilyId = lambda family_id: {5: SimpleNamespace(sample_id=5), 6: SimpleNamespace(sample_id=6)}

    response = client.get("/data/specific_export/family/3")

    assert response.status_code == 200
    assert "export_family_3.json" in response.headers["Content-disposition"]
    assert exports(fake_mcrit) == [[5, 6]]


def test_a_negative_id_still_reaches_the_backend(client, as_role, fake_mcrit):
    """mcrit gives query samples negative ids. The route took any string before, so a
    negative id reached the backend, and the int converter must not turn it into a 404."""
    as_role("contributor")
    fake_mcrit.getSampleById = lambda sample_id: SimpleNamespace(sample_id=sample_id)

    response = client.get("/data/specific_export/samples/-3")

    assert response.status_code == 200
    assert exports(fake_mcrit) == [[-3]]


if __name__ == "__main__":
    unittest.main()
