import random
from datetime import datetime,timezone
from src.config.database import Base,engine,Session
from src.models.entities import User,Shipment,Sample,ImportMapping
from src.utils.security import hash_password
from sqlalchemy import func
DEMO_MAPPING={'columns':{'shipment_code':'班次编号','route':'配送线路','zone':'温区','driver':'驾驶员','sample_code':'样本编号','exposure':'暴露时长','excursions':'超温次数','loss':'货损率'},'units':{'exposure':'minute','loss':'percent'}}
def seed():
 Base.metadata.create_all(engine);rng=random.Random(3102)
 with Session() as s:
  for role in ('admin','analyst','viewer'):
   email=role+'@demo.local'
   if not s.query(User).filter_by(email=email).first():s.add(User(email=email,role=role,password=hash_password('Demo123!')))
  s.commit()
  for i in range(60):
   code=f'XD-1115-{i+1:03}'
   ship=s.query(Shipment).filter_by(code=code).first()
   if not ship:
    ship=Shipment(code=code,route=f'鲜达线路 {i%12+1:02}',zone=('冷藏' if i<30 else '冷冻' if i<50 else '常温对照'),driver=f'驾驶员{i%12+1}');s.add(ship);s.flush()
   exposure=round(rng.uniform(3,85),1);loss=round(min(100,1+exposure*.11+rng.uniform(-.9,.9)),2)
   if i>=50:exposure=20
   if not s.query(Sample).filter_by(code=code+'-S').first():s.add(Sample(shipment_id=ship.id,code=code+'-S',exposure=None if i in (5,37) else exposure,excursions=int(exposure/10),loss=loss))
  if not s.query(ImportMapping).filter_by(name='承运商标准模板',version=1).first():
   s.add(ImportMapping(name='承运商标准模板',version=1,spec=DEMO_MAPPING,created=datetime.now(timezone.utc).isoformat()))
  s.commit();print({'shipments':s.query(Shipment).count(),'samples':s.query(Sample).count(),'users':s.query(User).count(),'mappings':s.query(ImportMapping).count()})
if __name__=='__main__':seed()
