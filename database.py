from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Float, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import json as json_module
import shutil
import os

Base = declarative_base()

class Abstract(Base):
    __tablename__ = 'abstracts'
    id = Column(Integer, primary_key=True)
    filename = Column(String(255))
    pdf_path = Column(String(512), nullable=True)
    json_data = Column(Text)
    edited_json_data = Column(Text, nullable=True)
    markdown_output = Column(Text)
    edited_markdown_output = Column(Text, nullable=True)
    pages_processed = Column(Integer)
    cost_estimate = Column(Float)
    processing_log = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_edited_at = Column(DateTime, nullable=True)
    edited_by = Column(String(100), nullable=True)
    is_edited = Column(Boolean, default=False)

class Database:
    def __init__(self, db_path='abstracts.db', storage_path='pdf_storage'):
        self.engine = create_engine(f'sqlite:///{db_path}')
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        self.storage_path = storage_path
        
        # Create storage directory
        os.makedirs(storage_path, exist_ok=True)
    
    def save_abstract(self, filename, json_data, markdown, pages, cost, user='system', pdf_path=None, processing_log=None):
        # Copy PDF to permanent storage
        stored_pdf_path = None
        if pdf_path and os.path.exists(pdf_path):
            stored_pdf_path = os.path.join(self.storage_path, f"{datetime.utcnow().timestamp()}_{filename}")
            shutil.copy2(pdf_path, stored_pdf_path)
        
        abstract = Abstract(
            filename=filename,
            pdf_path=stored_pdf_path,
            json_data=json_module.dumps(json_data),
            markdown_output=markdown,
            pages_processed=pages,
            cost_estimate=cost,
            processing_log=processing_log
        )
        self.session.add(abstract)
        self.session.commit()
        return abstract.id
    
    def update_abstract(self, abstract_id, edited_json, edited_markdown, user='system'):
        abstract = self.session.query(Abstract).filter_by(id=abstract_id).first()
        if abstract:
            abstract.edited_json_data = json_module.dumps(edited_json)
            abstract.edited_markdown_output = edited_markdown
            abstract.last_edited_at = datetime.utcnow()
            abstract.edited_by = user
            abstract.is_edited = True
            self.session.commit()
            return True
        return False
    
    def get_all_abstracts(self):
        return self.session.query(Abstract).order_by(Abstract.created_at.desc()).all()
    
    def get_abstract(self, abstract_id):
        return self.session.query(Abstract).filter_by(id=abstract_id).first()
    
    def get_pdf_path(self, abstract_id):
        abstract = self.get_abstract(abstract_id)
        if abstract and abstract.pdf_path and os.path.exists(abstract.pdf_path):
            return abstract.pdf_path
        return None
