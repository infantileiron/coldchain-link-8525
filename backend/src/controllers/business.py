from fastapi import HTTPException
from src.models.entities import Shipment,Sample,Study,ImportBatch,ImportRow
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
def ensure_batch(s,i,lock=False):
 q=s.query(ImportBatch).filter_by(id=i)
 if lock:q=q.with_for_update()
 row=q.first()
 if not row:raise HTTPException(404,'导入批次不存在')
 return row
def batch_detail(s,b):
 d=dump(b)
 d['rows']=[dump(r) for r in s.query(ImportRow).filter_by(batch_id=b.id).order_by(ImportRow.row_no).all()]
 return d
