from pydantic import BaseModel,Field
from fastapi import APIRouter,Request
router=APIRouter(prefix="/auth",tags=["auth"])
class DeviceRequest(BaseModel): installation_id:str=Field(min_length=8,max_length=160)
@router.post('/device')
def device(body:DeviceRequest,request:Request):
    token=request.app.state.token_service.issue("device:"+body.installation_id)
    return {"access_token":token,"token_type":"Bearer","expires_in":request.app.state.token_service.ttl}
