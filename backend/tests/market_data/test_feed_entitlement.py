import pytest

from app.market_data.feed_entitlement import resolve_feed_entitlement


def test_iex_is_never_labeled_consolidated():
    ent = resolve_feed_entitlement("iex", sip_entitled=False)
    assert ent.scope == "IEX_SINGLE_EXCHANGE"
    assert ent.consolidated is False
    assert "consolidated" not in ent.display_label.lower()


def test_sip_requires_entitlement():
    with pytest.raises(ValueError):
        resolve_feed_entitlement("sip", sip_entitled=False)


def test_entitled_sip_can_be_labeled_consolidated():
    ent = resolve_feed_entitlement("sip", sip_entitled=True)
    assert ent.scope == "SIP_CONSOLIDATED"
    assert ent.consolidated is True
    assert "consolidated" in ent.display_label.lower()
