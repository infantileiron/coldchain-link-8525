import csv,io,math
from sqlalchemy import func
from src.constants.enums import ZONES,EXPOSURE_UNITS,LOSS_UNITS
from src.models.entities import Shipment,Sample,ImportRow
CANONICAL=('shipment_code','route','zone','driver','sample_code','exposure','excursions','loss')
EXPOSURE_FACTOR={'minute':1,'hour':60,'second':1/60}
LOSS_FACTOR={'percent':1,'fraction':100}
LIMITS={'exposure':(0,1440),'excursions':(0,100),'loss':(0,100)}
MAX_ROWS=2000
def validate_spec(spec):
 if not isinstance(spec,dict):raise ValueError('映射定义必须是 JSON 对象')
 cols=spec.get('columns')
 if not isinstance(cols,dict):raise ValueError('columns 必须是对象：标准字段 → 表头列名')
 unknown=sorted(set(cols)-set(CANONICAL))
 if unknown:raise ValueError('未知标准字段：'+'、'.join(unknown))
 for f in ('shipment_code','sample_code'):
  if not cols.get(f):raise ValueError('columns 缺少必填字段 '+f)
 for k,v in cols.items():
  if v is not None and not isinstance(v,str):raise ValueError('列名必须是字符串：'+k)
 units=spec.get('units',{})
 if not isinstance(units,dict):raise ValueError('units 必须是对象：exposure/loss → 单位')
 unknown=sorted(set(units)-{'exposure','loss'})
 if unknown:raise ValueError('未知单位字段：'+'、'.join(unknown))
 if units.get('exposure') is not None and units['exposure'] not in EXPOSURE_UNITS:raise ValueError('exposure 单位必须是 minute / hour / second')
 if units.get('loss') is not None and units['loss'] not in LOSS_UNITS:raise ValueError('loss 单位必须是 percent / fraction')
def parse_csv(content):
 text=content.lstrip('\ufeff')
 try:reader=csv.DictReader(io.StringIO(text))
 except csv.Error:raise ValueError('CSV 解析失败，请确认是 UTF-8 逗号分隔文件')
 if not reader.fieldnames:raise ValueError('文件缺少表头行')
 rows=[]
 for row in reader:
  if row is None:continue
  cleaned={(k or '').strip():('' if v is None else str(v).strip()) for k,v in row.items()}
  if all(v=='' for v in cleaned.values()):continue
  rows.append(cleaned)
 if not rows:raise ValueError('文件没有数据行')
 if len(rows)>MAX_ROWS:raise ValueError(f'单批最多 {MAX_ROWS} 行，请拆分文件')
 return rows
def _number(raw,lo,hi):
 try:v=float(raw)
 except (ValueError,OverflowError):return None
 if not math.isfinite(v) or not lo<=v<=hi:return None
 return v
def normalize_row(raw,spec,shipment_codes,seen):
 """把一行原始数据按映射标准化。返回 (normalized|None, reasons)。
 reasons 为 [{code, detail}]；非空即隔离。单位不明、越界、归属缺失三类。"""
 reasons=[];cols=spec.get('columns',{});units=spec.get('units',{})
 def cell(field):
  name=cols.get(field)
  if not name:return None
  v=raw.get(name)
  if v is None:return None
  v=str(v).strip()
  return v or None
 shipment_code=cell('shipment_code');sample_code=cell('sample_code')
 if not shipment_code or not sample_code:
  reasons.append({'code':'attribution_missing','detail':'缺少班次编号或样本编号，无法建立归属'})
 ship=None
 if shipment_code:
  ship={'code':shipment_code,'route':cell('route'),'zone':cell('zone'),'driver':cell('driver')}
  if shipment_code not in shipment_codes:
   missing=[label for f,label in (('route','线路'),('zone','温区'),('driver','驾驶员')) if not ship[f]]
   if missing:reasons.append({'code':'attribution_missing','detail':'新班次缺少'+'、'.join(missing)+'，无法建立归属'})
  if ship['zone'] and ship['zone'] not in ZONES:
   reasons.append({'code':'out_of_range','detail':f"温区「{ship['zone']}」不在允许范围（{'、'.join(ZONES)}）"})
 if sample_code:
  if sample_code in seen:reasons.append({'code':'attribution_missing','detail':'批次内样本编号重复，归属不唯一'})
  seen.add(sample_code)
 sample={'code':sample_code,'exposure':None,'excursions':None,'loss':None}
 raw_exposure=cell('exposure')
 if raw_exposure is not None:
  unit=units.get('exposure')
  if not unit:reasons.append({'code':'unit_unknown','detail':'暴露时长未声明单位（minute/hour/second），无法确认是否把小时当分钟'})
  else:
   v=_number(raw_exposure,0,10**9)
   if v is None:reasons.append({'code':'out_of_range','detail':f'暴露时长「{raw_exposure}」不是有效数字'})
   else:
    v=round(v*EXPOSURE_FACTOR[unit],2);lo,hi=LIMITS['exposure']
    if not lo<=v<=hi:reasons.append({'code':'out_of_range','detail':f'暴露时长「{raw_exposure}」按 {unit} 换算为 {v} 分钟，越界（{lo}–{hi}）'})
    else:sample['exposure']=v
 raw_excursions=cell('excursions')
 if raw_excursions is not None:
  v=_number(raw_excursions,*LIMITS['excursions'])
  if v is None or v!=int(v):reasons.append({'code':'out_of_range','detail':f'超温次数「{raw_excursions}」越界（0–100 的整数）'})
  else:sample['excursions']=int(v)
 raw_loss=cell('loss')
 if raw_loss is not None:
  unit=units.get('loss')
  if not unit:reasons.append({'code':'unit_unknown','detail':'货损率未声明单位（percent/fraction）'})
  else:
   v=_number(raw_loss,0,10**9)
   if v is None:reasons.append({'code':'out_of_range','detail':f'货损率「{raw_loss}」不是有效数字'})
   else:
    v=round(v*LOSS_FACTOR[unit],4);lo,hi=LIMITS['loss']
    if not lo<=v<=hi:reasons.append({'code':'out_of_range','detail':f'货损率「{raw_loss}」按 {unit} 换算为 {v}%，越界（{lo}–{hi}）'})
    else:sample['loss']=v
 if reasons:return None,reasons
 return {'shipment':ship,'sample':sample},[]
def refresh_counts(s,batch):
 counts=dict(s.query(ImportRow.state,func.count()).filter_by(batch_id=batch.id).group_by(ImportRow.state).all())
 batch.raw_count=sum(counts.values())
 batch.qualified_count=counts.get('qualified',0)
 batch.quarantined_count=counts.get('quarantined',0)
 batch.imported_count=counts.get('imported',0)
 batch.conflict_count=counts.get('conflict',0)
def preview_batch(s,batch,mapping):
 """从原始行重放标准化。已入库与冲突保留行不重解释，但其样本编号仍参与批内去重。"""
 shipment_codes={c for (c,) in s.query(Shipment.code).all()}
 seen=set()
 code_col=mapping.spec.get('columns',{}).get('sample_code')
 rows=s.query(ImportRow).filter_by(batch_id=batch.id).order_by(ImportRow.row_no).all()
 for row in rows:
  if row.state in ('imported','conflict'):
   code=(row.raw.get(code_col) or '').strip() if code_col else ''
   if code:seen.add(code)
   continue
  normalized,reasons=normalize_row(row.raw,mapping.spec,shipment_codes,seen)
  row.mapping_version=mapping.version
  if reasons:row.state='quarantined';row.reasons=reasons;row.normalized=None
  else:row.state='qualified';row.reasons=[];row.normalized=normalized
 batch.mapping_version=mapping.version
 batch.state='previewed';batch.error=''
 refresh_counts(s,batch)
def _get_or_create_shipment(s,data,row_no,conflicts):
 ship=s.query(Shipment).filter_by(code=data['code']).with_for_update().first()
 if ship:
  diff=[label for f,label in (('route','线路'),('zone','温区'),('driver','驾驶员')) if data.get(f) and getattr(ship,f)!=data[f]]
  if diff:conflicts.append({'row_no':row_no,'code':data['code'],'reason':'班次'+'、'.join(diff)+'与现有记录不一致，保留现有班次信息'})
  return ship
 ship=Shipment(code=data['code'],route=data['route'],zone=data['zone'],driver=data['driver'])
 s.add(ship);s.flush()
 return ship
def publish_batch(s,batch,now):
 """单事务发布：合格行的班次与样本一起生效。已存在样本保留并记冲突。
 调用方负责 commit；IntegrityError 时整体回滚，重试即可恢复且不重复写入。"""
 conflicts=[]
 rows=s.query(ImportRow).filter_by(batch_id=batch.id,state='qualified').order_by(ImportRow.row_no).all()
 for row in rows:
  n=row.normalized;ship=_get_or_create_shipment(s,n['shipment'],row.row_no,conflicts)
  data=n['sample']
  if s.query(Sample).filter_by(code=data['code']).with_for_update().first():
   conflicts.append({'row_no':row.row_no,'code':data['code'],'reason':'样本编号已存在，保留现有样本内容（可能为手工修改）'})
   row.state='conflict';row.reasons=[{'code':'conflict','detail':'样本编号已存在，保留现有内容'}]
   continue
  sample=Sample(shipment_id=ship.id,code=data['code'],exposure=data['exposure'],excursions=data['excursions'],loss=data['loss'])
  s.add(sample);s.flush()
  row.state='imported';row.shipment_id=ship.id;row.sample_id=sample.id;row.reasons=[]
 batch.state='published';batch.published=now;batch.error=''
 batch.conflicts=conflicts
 refresh_counts(s,batch)
 return conflicts
