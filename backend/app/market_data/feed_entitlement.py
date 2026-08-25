from dataclasses import dataclass


@dataclass(frozen=True)
class FeedEntitlement:
    scope: str
    consolidated: bool
    display_label: str


def resolve_feed_entitlement(feed: str, *, sip_entitled: bool) -> FeedEntitlement:
    normalized = feed.strip().lower()
    if normalized == "iex":
        return FeedEntitlement(
            scope="IEX_SINGLE_EXCHANGE",
            consolidated=False,
            display_label="IEX single exchange",
        )
    if normalized == "sip":
        if not sip_entitled:
            raise ValueError("SIP feed requires ALPACA_SIP_ENTITLED=true")
        return FeedEntitlement(
            scope="SIP_CONSOLIDATED",
            consolidated=True,
            display_label="U.S. SIP consolidated",
        )
    raise ValueError("Alpaca feed must be iex or sip")
