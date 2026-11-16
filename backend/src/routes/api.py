import os,json
import redis
from fastapi import APIRouter,Depends,HTTPException,Response
from sqlalchemy.exc import IntegrityError
from src.config.database import db
from src.models.entities import User,Shipment,Sample,Study,Recommendation,Audit
from src.schemas.business import Login,ShipmentInput,SampleInput,StudyInput,RecommendationInput
from src.middlewares.auth import current,editor,admin
from src.utils.security import verify,token
from src.services.business import audit,dump
from src.controllers.business import ensure_shipment,ensure_study,study_rows
router=APIRouter()
@router.post('/auth/login')
def login(data:Login,s=Depends(db)):
 u=s.query(User).filter_by(email=data.email).first()
 if not u or not verify(data.password,u.password):raise HTTPException(401,'账号或密码错误')
 return {'token':token(u),'user':dump(u)}
@router.get('/me')
def me(u=Depends(current)):return dump(u)
@router.get('/shipments')
def ships(u=Depends(current),s=Depends(db)):return [dump(r) for r in s.query(Shipment).all()]
@router.post('/shipments')
def ship(data:ShipmentInput,u=Depends(editor),s=Depends(db)):
 r=Shipment(**data.model_dump());s.add(r)
 try:s.commit()
 except IntegrityError:s.rollback();raise HTTPException(409,'班次编号重复')
 audit(s,u,'创建班次 '+r.code);return dump(r)
@router.get('/samples')
def samples(u=Depends(current),s=Depends(db)):return [dump(r) for r in s.query(Sample).all()]
@router.post('/samples')
def sample(data:SampleInput,u=Depends(editor),s=Depends(db)):
 ensure_shipment(s,data.shipment_id);r=Sample(**data.model_dump());s.add(r)
 try:s.commit()
 except IntegrityError:s.rollback();raise HTTPException(409,'样本编号重复')
 audit(s,u,'录入样本 '+r.code);return dump(r)
@router.get('/studies')
def studies(u=Depends(current),s=Depends(db)):return [dump(r) for r in s.query(Study).order_by(Study.id.desc()).all()]
@router.post('/studies')
def study(data:StudyInput,u=Depends(editor),s=Depends(db)):
 rows=study_rows(s,data.zone);r=Study(**data.model_dump(),result={'snapshot':rows});s.add(r);s.commit()
 try:redis.Redis.from_url(os.environ['REDIS_URL']).rpush('studies',r.id)
 except redis.RedisError:
  r.state='failed';r.error='队列暂不可用，请重新创建研究';s.commit();raise HTTPException(503,r.error)
 audit(s,u,'提交研究 '+str(r.id));return dump(r)
@router.get('/studies/{i}')
def detail(i:int,u=Depends(current),s=Depends(db)):return dump(ensure_study(s,i))
@router.get('/studies/{i}/export')
def export(i:int,u=Depends(current),s=Depends(db)):
 r=ensure_study(s,i)
 if r.state!='done':raise HTTPException(409,'研究未成功完成')
 return Response(json.dumps(dump(r),ensure_ascii=False,indent=2),media_type='application/json',headers={'Content-Disposition':f'attachment; filename="coldchain-link-{i}.json"'})
@router.get('/recommendations')
def recs(u=Depends(current),s=Depends(db)):return [dump(r) for r in s.query(Recommendation).order_by(Recommendation.id.desc()).all()]
@router.post('/recommendations')
def rec(data:RecommendationInput,u=Depends(editor),s=Depends(db)):
 if ensure_study(s,data.study_id).state!='done':raise HTTPException(409,'仅已完成研究可以起草建议')
 r=Recommendation(**data.model_dump());s.add(r);s.commit();audit(s,u,'起草建议 '+str(r.id));return dump(r)
@router.post('/recommendations/{i}/approve')
def approve(i:int,u=Depends(admin),s=Depends(db)):
 r=s.get(Recommendation,i)
 if not r:raise HTTPException(404,'建议不存在')
 r.status='approved';s.commit();audit(s,u,'签核建议 '+str(i));return dump(r)
@router.get('/audits')
def audits(u=Depends(admin),s=Depends(db)):return [dump(r) for r in s.query(Audit).order_by(Audit.id.desc()).limit(100)]

@router.put('/shipments/{i}')
def edit_ship(i:int,data:ShipmentInput,u=Depends(editor),s=Depends(db)):
 row=s.get(Shipment,i)
 if not row:raise HTTPException(404,'班次不存在')
 for k,v in data.model_dump().items():setattr(row,k,v)
 try:s.commit()
 except IntegrityError:s.rollback();raise HTTPException(409,'班次编号重复')
 audit(s,u,'修改班次 '+str(i));return dump(row)
@router.put('/samples/{i}')
def edit_sample(i:int,data:SampleInput,u=Depends(editor),s=Depends(db)):
 row=s.get(Sample,i)
 if not row:raise HTTPException(404,'样本不存在')
 ensure_shipment(s,data.shipment_id)
 for k,v in data.model_dump().items():setattr(row,k,v)
 try:s.commit()
 except IntegrityError:s.rollback();raise HTTPException(409,'样本编号重复')
 audit(s,u,'修改样本 '+str(i));return dump(row)
