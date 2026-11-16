import os,json,hashlib
from datetime import datetime,timezone
import redis
from fastapi import APIRouter,Depends,HTTPException,Response
from sqlalchemy.exc import IntegrityError
from src.config.database import db
from src.models.entities import User,Shipment,Sample,Study,Recommendation,Audit,ImportMapping,ImportBatch,ImportRow
from src.schemas.business import Login,ShipmentInput,SampleInput,StudyInput,RecommendationInput,MappingInput,ImportUpload,PreviewInput
from src.middlewares.auth import current,editor,admin
from src.utils.security import verify,token
from src.services.business import audit,dump
from src.services.imports import validate_spec,parse_csv,preview_batch,publish_batch,refresh_counts
from src.controllers.business import ensure_shipment,ensure_study,study_rows,ensure_batch,batch_detail
router=APIRouter()
def now():return datetime.now(timezone.utc).isoformat()
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
@router.get('/mappings')
def mappings(u=Depends(current),s=Depends(db)):return [dump(r) for r in s.query(ImportMapping).order_by(ImportMapping.name,ImportMapping.version.desc()).all()]
@router.post('/mappings')
def mapping(data:MappingInput,u=Depends(editor),s=Depends(db)):
 try:validate_spec(data.spec)
 except ValueError as e:raise HTTPException(422,str(e))
 row=s.query(ImportMapping).filter_by(name=data.name,version=data.version).first()
 if row:
  if row.spec==data.spec:return dump(row)
  raise HTTPException(409,'该映射版本已存在且内容不同；映射版本不可变，修正请提升版本号')
 row=ImportMapping(name=data.name,version=data.version,spec=data.spec,created=now());s.add(row)
 try:s.commit()
 except IntegrityError:
  s.rollback();row=s.query(ImportMapping).filter_by(name=data.name,version=data.version).first()
  if row and row.spec==data.spec:return dump(row)
  raise HTTPException(409,'该映射版本已存在且内容不同；映射版本不可变，修正请提升版本号')
 audit(s,u,'创建导入映射 '+data.name+' v'+str(data.version));return dump(row)
@router.get('/imports')
def imports(u=Depends(current),s=Depends(db)):return [dump(r) for r in s.query(ImportBatch).order_by(ImportBatch.id.desc()).all()]
@router.post('/imports')
def upload(data:ImportUpload,u=Depends(editor),s=Depends(db)):
 m=s.get(ImportMapping,data.mapping_id)
 if not m:raise HTTPException(404,'导入映射不存在')
 try:rows=parse_csv(data.content)
 except ValueError as e:raise HTTPException(422,str(e))
 h=hashlib.sha256(data.content.encode()).hexdigest()
 existing=s.query(ImportBatch).filter_by(mapping_id=m.id,content_hash=h).first()
 if existing:return batch_detail(s,existing)
 b=ImportBatch(mapping_id=m.id,mapping_version=m.version,filename=data.filename,content_hash=h,state='pending',created_by=u.email,created=now())
 s.add(b);s.flush()
 for i,raw in enumerate(rows,1):s.add(ImportRow(batch_id=b.id,row_no=i,raw=raw,state='pending'))
 refresh_counts(s,b)
 try:s.commit()
 except IntegrityError:
  s.rollback();existing=s.query(ImportBatch).filter_by(mapping_id=m.id,content_hash=h).first()
  if existing:return batch_detail(s,existing)
  raise HTTPException(409,'批次上传冲突，请重试')
 audit(s,u,'上传导入批次 '+str(b.id)+'（'+str(len(rows))+' 行）');return batch_detail(s,b)
@router.get('/imports/{i}')
def import_detail(i:int,u=Depends(current),s=Depends(db)):return batch_detail(s,ensure_batch(s,i))
@router.post('/imports/{i}/preview')
def preview(i:int,data:PreviewInput|None=None,u=Depends(editor),s=Depends(db)):
 b=ensure_batch(s,i,lock=True)
 base=s.get(ImportMapping,b.mapping_id)
 if not base:raise HTTPException(404,'导入映射不存在')
 version=data.mapping_version if data else None
 if version is None:
  latest=s.query(ImportMapping).filter_by(name=base.name).order_by(ImportMapping.version.desc()).first()
  version=latest.version
 m=s.query(ImportMapping).filter_by(name=base.name,version=version).first()
 if not m:raise HTTPException(404,'映射版本不存在')
 preview_batch(s,b,m);s.commit()
 audit(s,u,'预览批次 '+str(i)+'（映射 '+m.name+' v'+str(m.version)+'）');return batch_detail(s,b)
@router.post('/imports/{i}/publish')
def publish(i:int,u=Depends(editor),s=Depends(db)):
 b=ensure_batch(s,i,lock=True)
 if b.state=='pending':raise HTTPException(409,'请先预览再发布')
 try:
  publish_batch(s,b,now());s.commit()
 except IntegrityError:
  s.rollback()
  b=ensure_batch(s,i);b.error='与并发写入冲突，本批未写入任何数据，请重试发布';s.commit()
  raise HTTPException(409,b.error)
 audit(s,u,'发布批次 '+str(i)+'（入库 '+str(b.imported_count)+' 行）');return batch_detail(s,b)
