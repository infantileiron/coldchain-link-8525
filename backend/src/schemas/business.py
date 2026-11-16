from pydantic import BaseModel,Field
from typing import Optional,Literal
class Login(BaseModel):
 email:str;password:str
class ShipmentInput(BaseModel):
 code:str=Field(min_length=1,max_length=60);route:str=Field(min_length=1,max_length=60);zone:Literal['冷藏','冷冻','常温对照'];driver:str=Field(min_length=1,max_length=60)
class SampleInput(BaseModel):
 shipment_id:int;code:str=Field(min_length=1,max_length=60);exposure:Optional[float]=Field(default=None,ge=0,le=1440);excursions:Optional[int]=Field(default=None,ge=0,le=100);loss:Optional[float]=Field(default=None,ge=0,le=100)
class StudyInput(BaseModel):
 name:str=Field(min_length=1,max_length=100);zone:Literal['冷藏','冷冻','常温对照'];feature:Literal['exposure','excursions']='exposure'
class RecommendationInput(BaseModel):
 study_id:int;note:str=Field(min_length=10,max_length=2000);owner:str=Field(min_length=1,max_length=60)
class MappingInput(BaseModel):
 name:str=Field(min_length=1,max_length=60);version:int=Field(ge=1);spec:dict
class ImportUpload(BaseModel):
 mapping_id:int;filename:str=Field(min_length=1,max_length=200);content:str=Field(min_length=1,max_length=2_000_000)
class PreviewInput(BaseModel):
 mapping_version:Optional[int]=Field(default=None,ge=1)
