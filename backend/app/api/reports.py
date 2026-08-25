from fastapi import APIRouter,Depends,Request
from app.market_data.service import get_market_data_provider,normalize_ticker
from app.prediction.service import build_hybrid_analysis
tech=APIRouter(prefix='/technical',tags=['technical']); fundamentals=APIRouter(prefix='/fundamentals',tags=['fundamentals']); news=APIRouter(prefix='/news',tags=['news']); verification=APIRouter(prefix='/verification',tags=['verification'])
async def _bundle(request,ticker,provider):return await build_hybrid_analysis(provider,normalize_ticker(ticker),evidence_service=getattr(request.app.state,'evidence_service',None))
@tech.get('/{ticker}')
async def technical_report(ticker:str,request:Request,provider=Depends(get_market_data_provider)):
    b=await _bundle(request,ticker,provider);return {'ticker':b.quote.ticker,'as_of':b.quote.normalized_timestamp,'score':b.technical.score,'completeness':b.technical.completeness,'indicators':b.technical.indicators,'evidence':b.technical.evidence}
@fundamentals.get('/{ticker}')
async def fundamental_report(ticker:str,request:Request,provider=Depends(get_market_data_provider)):
    b=await _bundle(request,ticker,provider);return {'ticker':b.quote.ticker,'as_of':b.quote.normalized_timestamp,'score':b.fundamental.score,'category':b.fundamental.category,'completeness':b.fundamental.completeness,'metrics':b.fundamental.metrics,'evidence':b.fundamental.evidence,'source':'SEC EDGAR' if b.fundamental.completeness else 'Unavailable'}
@news.get('/{ticker}')
async def news_report(ticker:str,request:Request,provider=Depends(get_market_data_provider)):
    b=await _bundle(request,ticker,provider); pos=sum(e.sentiment>0 for e in b.sentiment.events); neg=sum(e.sentiment<0 for e in b.sentiment.events); total=max(1,len(b.sentiment.events));
    return {'ticker':b.quote.ticker,'as_of':b.quote.normalized_timestamp,'sentiment_score':b.sentiment.score,'net_sentiment':b.sentiment.net_sentiment,'certainty':b.sentiment.certainty,'cluster_count':b.sentiment.cluster_count,'events_used':b.sentiment.events_used,'evidence':b.sentiment.evidence,'sentiment_split':{'positive':pos/total*100,'neutral':(total-pos-neg)/total*100,'negative':neg/total*100},'events':[e.__dict__ for e in b.sentiment.events]}
@verification.get('/{ticker}')
async def verification_report(ticker:str,request:Request,provider=Depends(get_market_data_provider)):
    b=await _bundle(request,ticker,provider);return {'ticker':b.quote.ticker,'as_of':b.quote.normalized_timestamp,'provider':b.quote.provider,'feed_scope':b.quote.feed_scope,'feed_label':b.quote.feed_label or b.quote.feed_scope,'consolidated':b.quote.consolidated,'source_agreement':b.validation.source_agreement,'freshness_seconds':b.quote.freshness_seconds,'data_quality':b.validation.data_quality,'completeness':b.validation.completeness,'reasons':b.validation.reasons}
