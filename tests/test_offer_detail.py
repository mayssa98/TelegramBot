"""Tests for offer detail formatting helpers."""

from bot import offer_detail_fields


def test_offer_detail_fields_parse_admin_description():
    fields = offer_detail_fields(
        "Type: Ready-Made Account\nWarranty: Full\nDuration : 30 Days\nMail : iCloud\nAccess : Full",
        "",
    )

    assert fields["access"] == "Full"
    assert fields["note"] == "Full"
    assert fields["duration"] == "30 Days"
    assert fields["mail"] == "iCloud"
