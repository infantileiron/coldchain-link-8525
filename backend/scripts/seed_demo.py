import random
from src.config.database import Base,engine,Session
from src.models.entities import User,Shipment,Sample
from src.utils.security import hash_password
from sqlalchemy import func
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
  s.commit();print({'shipments':s.query(Shipment).count(),'samples':s.query(Sample).count(),'users':s.query(User).count()})
if __name__=='__main__':seed()
