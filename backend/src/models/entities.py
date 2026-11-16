from sqlalchemy import Column,Integer,String,Float,JSON,Text,UniqueConstraint
from src.config.database import Base
class User(Base):
 __tablename__='users'
 id=Column(Integer,primary_key=True);email=Column(String(100),unique=True);password=Column(String(200));role=Column(String(20))
class Shipment(Base):
 __tablename__='shipments'
 id=Column(Integer,primary_key=True);code=Column(String(60),unique=True);route=Column(String(60));zone=Column(String(20));driver=Column(String(60))
class Sample(Base):
 __tablename__='samples'
 id=Column(Integer,primary_key=True);shipment_id=Column(Integer,index=True);code=Column(String(60),unique=True);exposure=Column(Float,nullable=True);excursions=Column(Integer,nullable=True);loss=Column(Float,nullable=True)
class Study(Base):
 __tablename__='studies'
 id=Column(Integer,primary_key=True);name=Column(String(100));zone=Column(String(20));feature=Column(String(30));state=Column(String(20),default='queued');result=Column(JSON,nullable=True);error=Column(Text,default='')
class Recommendation(Base):
 __tablename__='recommendations'
 id=Column(Integer,primary_key=True);study_id=Column(Integer);note=Column(Text);owner=Column(String(60));status=Column(String(20),default='draft')
class Audit(Base):
 __tablename__='audits'
 id=Column(Integer,primary_key=True);actor=Column(String(100));action=Column(String(200));created=Column(String(40))
class ImportMapping(Base):
 __tablename__='import_mappings'
 __table_args__=(UniqueConstraint('name','version'),)
 id=Column(Integer,primary_key=True);name=Column(String(60));version=Column(Integer);spec=Column(JSON);created=Column(String(40))
class ImportBatch(Base):
 __tablename__='import_batches'
 __table_args__=(UniqueConstraint('mapping_id','content_hash'),)
 id=Column(Integer,primary_key=True);mapping_id=Column(Integer,index=True);mapping_version=Column(Integer);filename=Column(String(200));content_hash=Column(String(64));state=Column(String(20),default='pending');raw_count=Column(Integer,default=0);qualified_count=Column(Integer,default=0);quarantined_count=Column(Integer,default=0);imported_count=Column(Integer,default=0);conflict_count=Column(Integer,default=0);conflicts=Column(JSON,nullable=True);error=Column(Text,default='');created_by=Column(String(100));created=Column(String(40));published=Column(String(40),nullable=True)
class ImportRow(Base):
 __tablename__='import_rows'
 __table_args__=(UniqueConstraint('batch_id','row_no'),)
 id=Column(Integer,primary_key=True);batch_id=Column(Integer,index=True);row_no=Column(Integer);raw=Column(JSON);state=Column(String(20),default='pending');reasons=Column(JSON,nullable=True);normalized=Column(JSON,nullable=True);mapping_version=Column(Integer,nullable=True);shipment_id=Column(Integer,nullable=True);sample_id=Column(Integer,nullable=True)
