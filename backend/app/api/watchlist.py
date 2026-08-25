from pydantic import BaseModel
from fastapi import APIRouter,Depends,Request
from app.security.auth import require_principal
from app.market_data.service import normalize_ticker
router=APIRouter(prefix='/watchlist',tags=['watchlist'])
class Mutation(BaseModel):ticker:str
@router.get('')
def get_watchlist(request:Request,principal:str=Depends(require_principal)):
    store=getattr(request.app.state,'sql_store',None)
    values=store.list_watchlist(principal) if store else sorted(request.app.state.watchlists.get(principal,set()))
    return {'principal':principal,'tickers':values}
@router.post('')
def add(body:Mutation,request:Request,principal:str=Depends(require_principal)):
    ticker=normalize_ticker(body.ticker);store=getattr(request.app.state,'sql_store',None)
    if store:store.add_watchlist(principal,ticker);values=store.list_watchlist(principal)
    else:request.app.state.watchlists.setdefault(principal,set()).add(ticker);values=sorted(request.app.state.watchlists[principal])
    return {'principal':principal,'tickers':values}
@router.delete('/{ticker}')
def remove(ticker:str,request:Request,principal:str=Depends(require_principal)):
    ticker=normalize_ticker(ticker);store=getattr(request.app.state,'sql_store',None)
    if store:store.remove_watchlist(principal,ticker);values=store.list_watchlist(principal)
    else:request.app.state.watchlists.setdefault(principal,set()).discard(ticker);values=sorted(request.app.state.watchlists[principal])
    return {'principal':principal,'tickers':values}
