from fastapi import HTTPException
from src.models.entities import Shipment,Sample,Study
from src.services.business import dump
def ensure_shipment(s,i):
 if not s.get(Shipment,i):raise HTTPException(404,'班次不存在')
def study_rows(s,zone):
 ids=[r.id for r in s.query(Shipment).filter_by(zone=zone).all()]
 return [dump(r) for r in s.query(Sample).filter(Sample.shipment_id.in_(ids)).all()]
def ensure_study(s,i):
 row=s.get(Study,i)
 if not row:raise HTTPException(404,'研究不存在')
 return row
