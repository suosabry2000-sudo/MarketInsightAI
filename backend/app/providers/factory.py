from app.settings import Settings
from app.providers.sec import SecProvider
from app.providers.news import AlpacaNewsProvider
from app.providers.fred import FredProvider
from app.providers.evidence import EvidenceService

def create_evidence_service(s:Settings):
    sec=SecProvider(s.SEC_USER_AGENT) if s.SEC_USER_AGENT else None
    fred=FredProvider(s.FRED_API_KEY) if s.FRED_API_KEY else None
    news=AlpacaNewsProvider(s.APCA_API_KEY_ID,s.APCA_API_SECRET_KEY) if s.MARKET_PROVIDER.lower()=="alpaca" and s.APCA_API_KEY_ID and s.APCA_API_SECRET_KEY else None
    return EvidenceService(sec=sec,news=news,fred=fred) if any((sec,news,fred)) else None
