from dataclasses import dataclass
from datetime import datetime
import re
from app.providers.news import NewsEvent

@dataclass(frozen=True)
class SentimentResult:
    score: float
    net_sentiment: float
    certainty: float
    cluster_count: int
    events_used: int
    evidence: list[str]
    events: list[NewsEvent]

def _key(headline:str): return re.sub(r"\W+"," ",headline.lower()).strip()

def analyze_news(events:list[NewsEvent],as_of:datetime)->SentimentResult:
    clusters={}
    for e in sorted((x for x in events if x.published_at<=as_of),key=lambda x:x.importance*x.relevance,reverse=True): clusters.setdefault(_key(e.headline),e)
    used=list(clusters.values())
    if not used:return SentimentResult(50,0,0,0,0,["No recent material news"],[])
    weights=[max(.01,e.relevance*e.importance*(1.4 if e.material else 1)) for e in used]; net=sum(e.sentiment*w for e,w in zip(used,weights))/sum(weights)
    score=max(0,min(100,50+net*40)); certainty=min(100,25+sum(weights)*25)
    ev=[f"{e.publisher}: {e.headline}" for e in used[:5]]
    return SentimentResult(score,net,certainty,len(used),len(used),ev,used)
