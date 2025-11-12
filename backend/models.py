
from sqlalchemy import Column, Integer, String, Text, ForeignKey, create_engine
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
Base = declarative_base()
engine = create_engine("sqlite:///./data.db", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
STAGES = ["DEV","DEMO","LT","PROD"]
class Task(Base):
    __tablename__="tasks"
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200), nullable=False)
    details = Column(Text, default="")
    status = Column(String(64), default="new")
    priority = Column(Integer, default=2)
    sort_order = Column(Integer, default=0)
    dev_color = Column(String(32), default="sky")
    demo_color = Column(String(32), default="sky")
    lt_color = Column(String(32), default="sky")
    prod_color = Column(String(32), default="sky")
    dev_status = Column(String(64), default="")
    demo_status = Column(String(64), default="")
    lt_status = Column(String(64), default="")
    prod_status = Column(String(64), default="")
    orphan_notes = Column(Text, default="")
    assignments = relationship("Assignment", back_populates="task", cascade="all, delete-orphan")
class Person(Base):
    __tablename__="people"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False, unique=True)
    assignments = relationship("Assignment", back_populates="person", cascade="all, delete-orphan")
class Assignment(Base):
    __tablename__="assignments"
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False, index=True)
    person_id = Column(Integer, ForeignKey("people.id"), nullable=False)
    stage = Column(String(16), nullable=False)
    comment = Column(Text, default="")
    task = relationship("Task", back_populates="assignments")
    person = relationship("Person", back_populates="assignments")
class JiraItem(Base):
    __tablename__="jira_items"
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False, index=True)
    key = Column(String(64), nullable=False)
    title = Column(String(200), default="")
    url = Column(String(300), default="")
