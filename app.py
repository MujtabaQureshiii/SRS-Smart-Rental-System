"""Smart Rental System — university pilot web application.
Run: python run.py. No external payment collection, identity service or SMS provider is assumed.
"""
from __future__ import annotations
import os, secrets, hashlib, hmac, argparse, csv, io
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from contextlib import asynccontextmanager
from urllib.parse import quote
from fastapi import FastAPI, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Numeric, Boolean, ForeignKey, Text, UniqueConstraint, func, select
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, Session
from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT=Path(__file__).resolve().parent
# Local demo may still use SQLite. Cloud deploys must use persistent PostgreSQL.
DEPLOYED = bool(os.environ.get('RENDER_SERVICE_ID')) or os.environ.get('SRS_DEPLOYMENT_MODE', '').strip().lower() == 'production'
DB_URL=os.environ.get('DATABASE_URL',f'sqlite:///{ROOT / "srs.db"}')
if DEPLOYED:
 if not DB_URL.startswith(('postgres://', 'postgresql://', 'postgresql+psycopg://')):
  raise RuntimeError('Cloud deployment requires DATABASE_URL pointing to persistent PostgreSQL (not SQLite).')
 if len(os.environ.get('SRS_SECRET_KEY', '')) < 32:
  raise RuntimeError('Cloud deployment requires SRS_SECRET_KEY with at least 32 characters.')
 if len(os.environ.get('SRS_STATION_TOKEN', '')) < 32:
  raise RuntimeError('Cloud deployment requires SRS_STATION_TOKEN with at least 32 characters.')
 if os.environ.get('SRS_HTTPS') != '1':
  raise RuntimeError('Cloud deployment requires SRS_HTTPS=1.')
if DB_URL.startswith('postgres://'):
 DB_URL='postgresql+psycopg://'+DB_URL[len('postgres://'):]
elif DB_URL.startswith('postgresql://'):
 DB_URL='postgresql+psycopg://'+DB_URL[len('postgresql://'):]
engine=create_engine(DB_URL,connect_args={'check_same_thread':False} if DB_URL.startswith('sqlite') else {},pool_pre_ping=True)
SessionLocal=sessionmaker(bind=engine,autoflush=False,expire_on_commit=False)
Base=declarative_base()

def now():return datetime.now(timezone.utc).replace(tzinfo=None)
def money(v):return f'PKR {Decimal(str(v or 0)):,.0f}'
def pw_hash(password):
 salt=secrets.token_hex(16); digest=hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),240000)
 return f'{salt}${digest.hex()}'
def pw_check(password,stored):
 try:
  salt,val=stored.split('$'); digest=hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),240000)
  return hmac.compare_digest(digest.hex(),val)
 except Exception:return False

class Student(Base):
 __tablename__='students'
 id=Column(Integer,primary_key=True);name=Column(String(120),nullable=False); enrollment=Column(String(60),unique=True,nullable=False);department=Column(String(120),nullable=False);email=Column(String(150));phone=Column(String(30));created_at=Column(DateTime,default=now)
class StudentVerification(Base):
 __tablename__='student_verifications'
 id=Column(Integer,primary_key=True)
 student_id=Column(Integer,ForeignKey('students.id'),unique=True,nullable=False)
 status=Column(String(20),default='pending',nullable=False)
 checked_at=Column(DateTime)
 operator_id=Column(Integer,ForeignKey('operators.id'))

class Operator(Base):
 __tablename__='operators'
 id=Column(Integer,primary_key=True);username=Column(String(60),unique=True,nullable=False);password_hash=Column(String(200),nullable=False);title=Column(String(90),default='Authorized Operator');active=Column(Boolean,default=True)
class LoginAudit(Base):
 __tablename__='login_audit'
 id=Column(Integer,primary_key=True);username=Column(String(60));success=Column(Boolean,default=False);source_ip=Column(String(80));created_at=Column(DateTime,default=now)

class Category(Base):
 __tablename__='categories'
 id=Column(Integer,primary_key=True);name=Column(String(80),unique=True,nullable=False);kind=Column(String(40));icon=Column(String(45));description=Column(String(250));assets=relationship('Asset',back_populates='category')
class Rate(Base):
 __tablename__='rates'
 id=Column(Integer,primary_key=True);category_id=Column(Integer,ForeignKey('categories.id'),nullable=False);label=Column(String(70));minutes=Column(Integer,nullable=False);amount=Column(Numeric(10,2),nullable=False);active=Column(Boolean,default=True);category=relationship('Category')
class Asset(Base):
 __tablename__='assets'
 id=Column(Integer,primary_key=True);code=Column(String(60),unique=True,nullable=False);category_id=Column(Integer,ForeignKey('categories.id'),nullable=False);status=Column(String(30),default='available');condition=Column(String(90),default='Good');supplier=Column(String(150));cost=Column(Numeric(10,2),default=0);serial=Column(String(100));warranty=Column(String(150));note=Column(String(300));category=relationship('Category',back_populates='assets')
class Rental(Base):
 __tablename__='rentals'
 id=Column(Integer,primary_key=True);token=Column(String(80),unique=True,nullable=False);student_id=Column(Integer,ForeignKey('students.id'));category_id=Column(Integer,ForeignKey('categories.id'));rate_id=Column(Integer,ForeignKey('rates.id'));asset_id=Column(Integer,ForeignKey('assets.id'));amount=Column(Numeric(10,2));status=Column(String(35),default='pending');created_at=Column(DateTime,default=now);issued_at=Column(DateTime);due_at=Column(DateTime);returned_at=Column(DateTime);verified_by=Column(Integer,ForeignKey('operators.id'));id_checked=Column(Boolean,default=False);condition_out=Column(String(120));condition_in=Column(String(120));return_note=Column(String(400));student=relationship('Student');category=relationship('Category');rate=relationship('Rate');asset=relationship('Asset')
class Payment(Base):
 __tablename__='payments'
 id=Column(Integer,primary_key=True);rental_id=Column(Integer,ForeignKey('rentals.id'));method=Column(String(20));amount=Column(Numeric(10,2));status=Column(String(25),default='pending');reference=Column(String(100));verified_at=Column(DateTime);operator_id=Column(Integer,ForeignKey('operators.id'))
class Deposit(Base):
 __tablename__='deposits'
 id=Column(Integer,primary_key=True);rental_id=Column(Integer,ForeignKey('rentals.id'),unique=True);amount=Column(Numeric(10,2));status=Column(String(30),default='held');collected_at=Column(DateTime,default=now);released_at=Column(DateTime);operator_id=Column(Integer,ForeignKey('operators.id'))
class Event(Base):
 __tablename__='events'
 id=Column(Integer,primary_key=True);rental_id=Column(Integer,ForeignKey('rentals.id'));type=Column(String(50));notes=Column(String(500));created_at=Column(DateTime,default=now);operator_id=Column(Integer,ForeignKey('operators.id'))
class Inspection(Base):
 __tablename__='inspections'
 id=Column(Integer,primary_key=True);asset_id=Column(Integer,ForeignKey('assets.id'));rental_id=Column(Integer,ForeignKey('rentals.id'));condition=Column(String(100));action=Column(String(300));operator_id=Column(Integer,ForeignKey('operators.id'));created_at=Column(DateTime,default=now)
class Expense(Base):
 __tablename__='expenses'
 id=Column(Integer,primary_key=True);category=Column(String(70));amount=Column(Numeric(10,2));description=Column(String(240));created_at=Column(DateTime,default=now);operator_id=Column(Integer,ForeignKey('operators.id'))
class Approval(Base):
 __tablename__='approvals'
 id=Column(Integer,primary_key=True);rental_id=Column(Integer,ForeignKey('rentals.id'));type=Column(String(40));reason=Column(String(500));status=Column(String(25),default='pending');requested_by=Column(Integer,ForeignKey('operators.id'));decided_by=Column(Integer,ForeignKey('operators.id'));created_at=Column(DateTime,default=now);decided_at=Column(DateTime)
class Check(Base):
 __tablename__='checks'
 id=Column(Integer,primary_key=True);kind=Column(String(35));stock_ok=Column(Boolean);power_ok=Column(Boolean);qr_ok=Column(Boolean);cash_ok=Column(Boolean);notes=Column(String(500));created_at=Column(DateTime,default=now);operator_id=Column(Integer,ForeignKey('operators.id'))

SEED=[('Basic Calculator','calculator',2,[(60,130,'1 hour'),(180,280,'3-hour session')]),('Scientific Calculator','calculator',3,[(60,180,'1 hour'),(180,420,'3-hour session')]),('USB Drive','usb',3,[(60,130,'1 hour'),(1440,250,'1 day')]),('Power Bank','battery-charging',4,[(60,180,'1 hour'),(180,380,'3-hour session')]),('Charger / Cable Set','plug',5,[(60,100,'1 hour'),(180,250,'3-hour session')]),('Umbrella','umbrella',5,[(180,180,'Session (provisional duration)'),(1440,300,'1 day')])]
# The original plan specifies 5 total calculators but does not define a basic/scientific split.
# Default 2/3 can be edited in inventory. Umbrella session length is PROVISIONAL pending policy confirmation.
def seed(db):
 if db.query(Category).count():return
 costs={'Basic Calculator':3500,'Scientific Calculator':3500,'USB Drive':2000,'Power Bank':4000,'Charger / Cable Set':1500,'Umbrella':1600}
 for name,icon,n,rates in SEED:
  c=Category(name=name,icon=icon,kind=icon);db.add(c);db.flush()
  for mins,amt,label in rates:db.add(Rate(category_id=c.id,label=label,minutes=mins,amount=amt))
  for j in range(1,n+1):db.add(Asset(code=f'SRS-{c.id:02d}-{j:03d}',category_id=c.id,cost=costs[name]))
 db.commit()

def initdb():
 Base.metadata.create_all(engine)
 with SessionLocal() as db:
  seed(db)
  # Render Free does not offer shell access; optional first-deploy account bootstrap.
  # The password is stored only as a salted hash; remove bootstrap env vars afterward.
  username=os.environ.get('SRS_INITIAL_OPERATOR_USER','').strip()
  password=os.environ.get('SRS_INITIAL_OPERATOR_PASSWORD','')
  if username or password:
   if not username or len(username)>60 or len(password)<12:
    raise RuntimeError('SRS initial operator credentials must include a username and a password of at least 12 characters')
   if not db.query(Operator).first():
    db.add(Operator(username=username,password_hash=pw_hash(password),title='Authorized Operator'))
    db.commit()

@asynccontextmanager
async def lifespan(app):
 initdb();yield
app=FastAPI(title='Smart Rental System (SRS)',lifespan=lifespan,docs_url=None,redoc_url=None,openapi_url=None)
app.mount('/static',StaticFiles(directory=str(ROOT/'static')),name='static')
jinja=Environment(loader=FileSystemLoader(str(ROOT/'templates')),autoescape=select_autoescape(['html','xml']))
jinja.filters['money']=money

PHOTO_FILES={
 'Basic Calculator':'Simple_Calculator.jpg',
 'Scientific Calculator':'Scientific_calculator_casio.jpg',
 'USB Drive':'USB_Flash_Drives.jpg',
 'Power Bank':'Portable_power_bank.jpg',
 'Charger / Cable Set':'MobileUsbCharger.jpg',
 'Umbrella':'Black_umbrella.jpg',
}
PHOTO_SLUGS={
 'Basic Calculator':'basic-calculator','Scientific Calculator':'scientific-calculator',
 'USB Drive':'usb-drive','Power Bank':'power-bank',
 'Charger / Cable Set':'charger-cable-set','Umbrella':'umbrella'
}
def photo_url(name):
 slug=PHOTO_SLUGS.get(name,'')
 return '/static/photos/'+slug+'.jpg' if slug else ''
def remote_photo(name):
 filename=PHOTO_FILES.get(name)
 return 'https://commons.wikimedia.org/wiki/Special:FilePath/'+quote(filename)+'?width=520' if filename else ''
jinja.filters['product_photo']=photo_url
jinja.filters['product_photo_remote']=remote_photo
jinja.filters['dt']=lambda v: v.strftime('%d %b %Y, %I:%M %p') if v else '—'

def db_dep():
 with SessionLocal() as db:yield db

def html(req,name,**ctx):
 sess=req.session
 return HTMLResponse(jinja.get_template(name).render(request=req,csrf=sess.get('csrf'),current_student=sess.get('student_id'),operator=sess.get('operator'),**ctx))
def go(url):return RedirectResponse(url,status_code=303)
def flash(req,msg,typ='success'):req.session['flash']=(msg,typ)
def pull_flash(req):return req.session.pop('flash',None)
def check_csrf(req,csrf):
 if not csrf or not hmac.compare_digest(str(csrf),str(req.session.get('csrf',''))):raise HTTPException(403,'Invalid form token. Refresh the page and retry.')
def admin(req,db):
 op=req.session.get('operator');o=db.get(Operator,op) if op else None
 if not o or not o.active:raise HTTPException(401,'Authorized operator login required. Open /operator/login')
 return o

def logged_event(db,rid,typ,operator_id=None,notes=''):db.add(Event(rental_id=rid,type=typ,operator_id=operator_id,notes=notes))
def student_is_verified(db,sid):
 v=db.query(StudentVerification).filter_by(student_id=sid).first() if sid else None
 return bool(v and v.status=='verified')

def station_token():
 configured=os.environ.get('SRS_STATION_TOKEN','').strip()
 if configured:
  if len(configured)<32:raise RuntimeError('SRS_STATION_TOKEN must be at least 32 characters')
  return configured
 f=ROOT/'.srs_station_token'
 if not f.exists():f.write_text(secrets.token_urlsafe(24))
 return f.read_text().strip()

def upcoming(r):return r.due_at and r.status=='active' and now()>r.due_at+timedelta(minutes=15)

def update_due(db):
 active=db.query(Rental).filter(Rental.status=='active',Rental.due_at!=None).all()
 for r in active:
  if upcoming(r):r.status='overdue'
 db.commit()

def session_secret():
 key=os.environ.get('SRS_SECRET_KEY')
 if key:return key
 f=ROOT/'.srs_secret'
 if not f.exists():
  f.write_text(secrets.token_urlsafe(48),encoding='utf8')
  try:os.chmod(f,0o600)
  except OSError:pass
 return f.read_text(encoding='utf8').strip()

@app.middleware('http')
async def setup(req,call_next):
 if 'csrf' not in req.session:req.session['csrf']=secrets.token_urlsafe(25)
 response=await call_next(req)
 response.headers['X-Content-Type-Options']='nosniff';response.headers['X-Frame-Options']='DENY';response.headers['Referrer-Policy']='strict-origin-when-cross-origin';response.headers['Content-Security-Policy']="default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; img-src 'self' data: https://commons.wikimedia.org https://upload.wikimedia.org; font-src 'self'; form-action 'self'; frame-ancestors 'none'"
 return response

app.add_middleware(SessionMiddleware,secret_key=session_secret(),same_site='lax',https_only=os.environ.get('SRS_HTTPS','0')=='1')

@app.get('/',response_class=HTMLResponse)
def welcome(req:Request,db:Session=Depends(db_dep)):
 return html(req,'welcome.html',station_scanned=bool(req.session.get('station_scanned')),flash=pull_flash(req))

@app.get('/station/{access_code}')
def qr_entry(req:Request,access_code:str):
 # An SRS station QR encodes this URL. The phone camera opens it in a browser.
 if not hmac.compare_digest(access_code,station_token()):raise HTTPException(404,'Invalid station QR')
 req.session['station_scanned']=True
 flash(req,'Station QR scanned. Register your student details to continue.')
 return go('/#register')

@app.get('/operator/station-qr')
def station_qr_page(req:Request,db:Session=Depends(db_dep),base_url:str=''):
 o=admin(req,db)
 origin=base_url.rstrip('/') or os.environ.get('SRS_PUBLIC_URL','').rstrip('/') or str(req.base_url).rstrip('/')
 from urllib.parse import urlsplit
 parsed=urlsplit(origin)
 if parsed.scheme not in ('http','https') or (DEPLOYED and parsed.scheme!='https') or not parsed.hostname or parsed.username or parsed.password or len(origin)>250:raise HTTPException(400,'Enter a valid HTTP/HTTPS base URL')
 qr_url=origin+'/station/'+station_token()
 return html(req,'station_qr.html',op=o,qr_url=qr_url,base_url=origin,page='station_qr',flash=pull_flash(req))

@app.get('/operator/station-qr/image.png')
def station_qr_image(req:Request,db:Session=Depends(db_dep),base_url:str=''):
 admin(req,db)
 import qrcode
 from urllib.parse import urlsplit
 origin=base_url.rstrip('/') or os.environ.get('SRS_PUBLIC_URL','').rstrip('/') or str(req.base_url).rstrip('/')
 parsed=urlsplit(origin)
 if parsed.scheme not in ('http','https') or (DEPLOYED and parsed.scheme!='https') or not parsed.hostname or parsed.username or parsed.password or len(origin)>250:raise HTTPException(400,'Invalid URL')
 qr=qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H,box_size=10,border=4)
 qr.add_data(origin+'/station/'+station_token());qr.make(fit=True)
 img=qr.make_image(fill_color='#172747',back_color='white')
 image_bytes=io.BytesIO();img.save(image_bytes,format='PNG')
 return Response(image_bytes.getvalue(),media_type='image/png',headers={'Cache-Control':'no-store'})
@app.post('/register')
def register(req:Request,name:str=Form(...),enrollment:str=Form(...),department:str=Form(...),email:str=Form(''),phone:str=Form(''),csrf:str=Form(...),db:Session=Depends(db_dep)):
 check_csrf(req,csrf)
 if not req.session.get('station_scanned'):raise HTTPException(403,'Scan the SRS station QR code before registering.')
 name=name.strip();enrollment=enrollment.strip().upper();department=department.strip()
 if not all([name,enrollment,department]) or len(name)>120 or len(enrollment)>60 or len(department)>120:raise HTTPException(400,'Invalid registration details')
 stu=db.query(Student).filter_by(enrollment=enrollment).first()
 if stu:
  # Prevent account takeover by knowing an enrollment number. Reuse requires exact name AND department.
  if stu.name.casefold()!=name.casefold() or stu.department.casefold()!=department.casefold():raise HTTPException(409,'Registration details do not match an existing enrollment. Ask the operator for assistance.')
 else:
  stu=Student(name=name,enrollment=enrollment,department=department,email=email.strip()[:150] or None,phone=phone.strip()[:30] or None);db.add(stu);db.commit();db.refresh(stu)
 v=db.query(StudentVerification).filter_by(student_id=stu.id).first()
 if not v:v=StudentVerification(student_id=stu.id,status='pending');db.add(v)
 else:v.status='pending';v.checked_at=None;v.operator_id=None
 db.commit()
 req.session['student_id']=stu.id
 flash(req,'Registration saved. Please show your physical university ID to the station operator.')
 return go('/verification')
@app.get('/verification')
def verification_wait(req:Request,db:Session=Depends(db_dep)):
 sid=req.session.get('student_id')
 if not sid:return go('/')
 return html(req,'verification.html',student=db.get(Student,sid),verified=student_is_verified(db,sid),flash=pull_flash(req))

@app.get('/items')
def items(req:Request,db:Session=Depends(db_dep)):
 cats=db.query(Category).order_by(Category.id).all();rates=db.query(Rate).filter_by(active=True).all();stock={c.id:db.query(Asset).filter_by(category_id=c.id,status='available').count() for c in cats}
 return html(req,'items.html',categories=cats,rates=rates,stock=stock,verified=student_is_verified(db,req.session.get('student_id')),flash=pull_flash(req),student=db.get(Student,req.session.get('student_id')) if req.session.get('student_id') else None)
@app.get('/select/{category_id}')
def select_item(req:Request,category_id:int,db:Session=Depends(db_dep)):
 if not req.session.get('student_id'):flash(req,'Scan the station QR and register first.','warning');return go('/')
 if not student_is_verified(db,req.session['student_id']):flash(req,'Physical student ID verification is required before selecting items.','warning');return go('/verification')
 cat=db.get(Category,category_id)
 if not cat:raise HTTPException(404)
 rates=db.query(Rate).filter_by(category_id=cat.id,active=True).all()
 available=db.query(Asset).filter_by(category_id=cat.id,status='available').count()
 return html(req,'select.html',category=cat,rates=rates,available=available,flash=pull_flash(req))
@app.post('/rentals/request')
def rental_request(req:Request,category_id:int=Form(...),rate_id:int=Form(...),method:str=Form(...),csrf:str=Form(...),db:Session=Depends(db_dep)):
 check_csrf(req,csrf);sid=req.session.get('student_id')
 if not sid:raise HTTPException(403,'Please register first')
 if not req.session.get('station_scanned') or not student_is_verified(db,sid):raise HTTPException(403,'Station QR access and operator ID verification are required before borrowing')
 c=db.get(Category,category_id);rate=db.get(Rate,rate_id)
 if not c or not rate or rate.category_id!=c.id or not rate.active:raise HTTPException(400,'Invalid selection')
 if method not in ('cash','jazzcash','easypaisa'):raise HTTPException(400,'Invalid payment method')
 if not db.query(Asset).filter_by(category_id=c.id,status='available').first():raise HTTPException(409,'Currently out of stock')
 rental=Rental(student_id=sid,category_id=c.id,rate_id=rate.id,amount=rate.amount,token=secrets.token_urlsafe(28),status='pending')
 db.add(rental);db.flush();db.add(Payment(rental_id=rental.id,method=method,amount=rate.amount,status='pending'));logged_event(db,rental.id,'requested',notes=f'Payment method: {method}');db.commit()
 req.session['last_rental']=rental.token;return go(f'/rental/{rental.token}')
@app.get('/rental/{token}')
def rental_view(req:Request,token:str,db:Session=Depends(db_dep)):
 r=db.query(Rental).filter_by(token=token).first()
 if not r:raise HTTPException(404)
 if req.session.get('student_id')!=r.student_id and req.session.get('operator') is None:raise HTTPException(403,'This rental belongs to another student')
 p=db.query(Payment).filter_by(rental_id=r.id).first();deposit=db.query(Deposit).filter_by(rental_id=r.id).first();events=db.query(Event).filter_by(rental_id=r.id).order_by(Event.id.desc()).all()
 return html(req,'rental.html',r=r,p=p,deposit=deposit,events=events,flash=pull_flash(req))
@app.post('/rental/{token}/support')
def rental_support(req:Request,token:str,kind:str=Form(...),details:str=Form(...),csrf:str=Form(...),db:Session=Depends(db_dep)):
 check_csrf(req,csrf);r=db.query(Rental).filter_by(token=token).first()
 if not r or req.session.get('student_id')!=r.student_id:raise HTTPException(403)
 if kind not in ('extension_request','fault_report','return_dispute'):raise HTTPException(400)
 if not details.strip():raise HTTPException(400,'Add a short explanation')
 logged_event(db,r.id,kind,notes=details.strip()[:500]);db.commit();flash(req,'Your request has been recorded for the station operator.');return go(f'/rental/{token}')
@app.get('/operator/login')
def login(req:Request):return html(req,'login.html',flash=pull_flash(req))
@app.post('/operator/login')
def login_submit(req:Request,username:str=Form(...),password:str=Form(...),csrf:str=Form(...),db:Session=Depends(db_dep)):
 check_csrf(req,csrf)
 username=username.strip()[:60];ip=(req.client.host if req.client else 'unknown')[:80]
 failures=db.query(LoginAudit).filter(LoginAudit.username==username,LoginAudit.source_ip==ip,LoginAudit.success==False,LoginAudit.created_at>=now()-timedelta(minutes=15)).count()
 if failures>=5:
  flash(req,'Too many unsuccessful attempts. Try again in 15 minutes.','danger');return go('/operator/login')
 o=db.query(Operator).filter_by(username=username).first()
 success=bool(o and o.active and pw_check(password,o.password_hash))
 db.add(LoginAudit(username=username,source_ip=ip,success=success));db.commit()
 if not success:flash(req,'Incorrect username or password.','danger');return go('/operator/login')
 req.session.clear();req.session['csrf']=secrets.token_urlsafe(25);req.session['operator']=o.id;flash(req,'Welcome to the SRS operator panel.');return go('/operator')
@app.post('/operator/logout')
def logout(req:Request,csrf:str=Form(...)):
 check_csrf(req,csrf);req.session.clear();return go('/operator/login')
@app.get('/operator')
def dashboard(req:Request,db:Session=Depends(db_dep)):
 op=admin(req,db);update_due(db)
 rentals=db.query(Rental).order_by(Rental.id.desc()).limit(7).all()
 stats={'students':db.query(Student).count(),'inventory':db.query(Asset).count(),'available':db.query(Asset).filter_by(status='available').count(),'active':db.query(Rental).filter(Rental.status.in_(['active','overdue'])).count(),'overdue':db.query(Rental).filter_by(status='overdue').count(),'completed':db.query(Rental).filter_by(status='completed').count(),'pending':db.query(Rental).filter_by(status='pending').count(),'collected':db.query(func.coalesce(func.sum(Payment.amount),0)).filter(Payment.status=='verified').scalar(),'held':db.query(func.coalesce(func.sum(Deposit.amount),0)).filter(Deposit.status=='held').scalar()}
 # Option 2 GUI: read-only charts computed from existing inventory and rental records.
 # No new tables, business rules, privileges, or mutation actions are introduced.
 asset_statuses=dict(db.query(Asset.status,func.count(Asset.id)).group_by(Asset.status).all())
 used=asset_statuses.get('rented',0)
 not_ready=sum(n for status,n in asset_statuses.items() if status not in ('available','rented'))
 total=max(1,stats['inventory'])
 available_end=100*stats['available']/total
 rented_end=100*(stats['available']+used)/total
 donut_style=f'conic-gradient(#123861 0 {available_end:.3f}%, #f1ba43 {available_end:.3f}% {rented_end:.3f}%, #aec2d6 {rented_end:.3f}% 100%)'
 days=[(now()-timedelta(days=6-i)).date() for i in range(7)]
 recent_dates=db.query(Rental.created_at).filter(Rental.created_at>=datetime.combine(days[0],datetime.min.time())).all()
 counts_by_date={d:0 for d in days}
 for (created_at,) in recent_dates:
  if created_at and created_at.date() in counts_by_date:counts_by_date[created_at.date()]+=1
 heights=[counts_by_date[d] for d in days]
 chart_max=max(1,*heights)
 dots=[{'x':20+i*100,'y':round(147-(c/chart_max)*112,1),'value':c} for i,c in enumerate(heights)]
 chart_points=' '.join(f'{point["x"]},{point["y"]}' for point in dots)
 chart_labels=[d.strftime('%a') for d in days]
 return html(req,'dashboard.html',op=op,stats=stats,rentals=rentals,asset_view={'rented':used,'not_ready':not_ready,'donut_style':donut_style},chart_points=chart_points,chart_dots=dots,chart_labels=chart_labels,chart_total=sum(heights),flash=pull_flash(req),page='dashboard')
@app.get('/operator/access')
def access_log(req:Request,db:Session=Depends(db_dep)):
 op=admin(req,db)
 return html(req,'access.html',op=op,records=db.query(LoginAudit).order_by(LoginAudit.id.desc()).limit(100).all(),operators=db.query(Operator).order_by(Operator.id).all(),flash=pull_flash(req),page='access')

@app.get('/operator/students')
def students(req:Request,q:str='',db:Session=Depends(db_dep)):
 op=admin(req,db);query=db.query(Student)
 if q:query=query.filter((Student.name.ilike(f'%{q}%'))|(Student.enrollment.ilike(f'%{q}%')))
 return html(req,'students.html',op=op,students=query.order_by(Student.id.desc()).limit(200).all(),q=q,verification_map={v.student_id:v for v in db.query(StudentVerification).all()},flash=pull_flash(req),page='students')
@app.post('/operator/students/{student_id}/verify')
def verify_student(req:Request,student_id:int,csrf:str=Form(...),db:Session=Depends(db_dep)):
 o=admin(req,db);check_csrf(req,csrf)
 stu=db.get(Student,student_id)
 if not stu:raise HTTPException(404)
 v=db.query(StudentVerification).filter_by(student_id=student_id).first()
 if not v:v=StudentVerification(student_id=student_id);db.add(v)
 v.status='verified';v.checked_at=now();v.operator_id=o.id
 db.commit();flash(req,f'Physical ID verified for {stu.enrollment}. Student may now select a rental.')
 return go('/operator/students')

@app.get('/operator/inventory')
def inventory(req:Request,db:Session=Depends(db_dep)):
 op=admin(req,db);return html(req,'inventory.html',op=op,assets=db.query(Asset).order_by(Asset.id).all(),categories=db.query(Category).all(),flash=pull_flash(req),page='inventory')
@app.post('/operator/inventory')
def add_asset(req:Request,code:str=Form(...),category_id:int=Form(...),supplier:str=Form(''),cost:float=Form(0),serial:str=Form(''),warranty:str=Form(''),csrf:str=Form(...),db:Session=Depends(db_dep)):
 admin(req,db);check_csrf(req,csrf)
 if not db.get(Category,category_id) or not code.strip() or cost<0:raise HTTPException(400,'Invalid asset details')
 if db.query(Asset).filter_by(code=code.strip()).first():raise HTTPException(409,'Asset ID already exists')
 db.add(Asset(code=code.strip()[:60],category_id=category_id,supplier=supplier[:150],cost=Decimal(str(cost)),serial=serial[:100],warranty=warranty[:150]));db.commit();flash(req,'Asset added to inventory.');return go('/operator/inventory')
@app.post('/operator/inventory/{asset_id}/status')
def asset_status(req:Request,asset_id:int,status:str=Form(...),condition:str=Form(...),note:str=Form(''),csrf:str=Form(...),db:Session=Depends(db_dep)):
 o=admin(req,db);check_csrf(req,csrf);asset=db.get(Asset,asset_id)
 if not asset:raise HTTPException(404)
 if status not in ('available','maintenance','damaged','unavailable'):raise HTTPException(400)
 if db.query(Rental).filter(Rental.asset_id==asset.id,Rental.status.in_(['active','overdue'])).first():raise HTTPException(409,'Cannot change status while item is rented')
 asset.status=status;asset.condition=condition[:90];asset.note=note[:300];db.add(Inspection(asset_id=asset.id,condition=condition[:90],action=f'Status set to {status}. {note[:200]}',operator_id=o.id));db.commit();flash(req,'Asset record updated.');return go('/operator/inventory')
@app.get('/operator/rentals')
def rentals_list(req:Request,status:str='',db:Session=Depends(db_dep)):
 op=admin(req,db);update_due(db);q=db.query(Rental)
 if status in ('pending','active','overdue','completed'):q=q.filter_by(status=status)
 return html(req,'rentals.html',op=op,rentals=q.order_by(Rental.id.desc()).limit(300).all(),status=status,flash=pull_flash(req),page='rentals')
@app.get('/operator/rentals/{rid}')
def manage_rental(req:Request,rid:int,db:Session=Depends(db_dep)):
 op=admin(req,db);update_due(db);r=db.get(Rental,rid)
 if not r:raise HTTPException(404)
 assets=db.query(Asset).filter_by(category_id=r.category_id,status='available').all();p=db.query(Payment).filter_by(rental_id=r.id).first();deposit=db.query(Deposit).filter_by(rental_id=r.id).first();events=db.query(Event).filter_by(rental_id=r.id).order_by(Event.id.desc()).all();approvals=db.query(Approval).filter_by(rental_id=r.id).all()
 return html(req,'manage_rental.html',op=op,r=r,assets=assets,p=p,deposit=deposit,events=events,approvals=approvals,flash=pull_flash(req),page='rentals')
@app.post('/operator/rentals/{rid}/issue')
def issue(req:Request,rid:int,asset_id:int=Form(...),id_checked:str=Form(''),payment_verified:str=Form(''),reference:str=Form(''),deposit_amount:str=Form('0'),csrf:str=Form(...),db:Session=Depends(db_dep)):
 o=admin(req,db);check_csrf(req,csrf);r=db.get(Rental,rid)
 if not r or r.status!='pending':raise HTTPException(409,'This rental is not pending')
 if not student_is_verified(db,r.student_id):raise HTTPException(403,'Physical student ID must be verified before issuing a rental')
 if id_checked!='yes' or payment_verified!='yes':raise HTTPException(400,'Physical student ID and payment must both be verified')
 try:dep=Decimal(deposit_amount)
 except:raise HTTPException(400,'Invalid deposit amount')
 if dep<0 or dep>100000:raise HTTPException(400,'Invalid deposit amount')
 # Conditional update provides atomic protection against double-issuance.
 changed=db.query(Asset).filter(Asset.id==asset_id,Asset.category_id==r.category_id,Asset.status=='available').update({'status':'rented'},synchronize_session=False)
 if changed!=1:db.rollback();raise HTTPException(409,'Item is not available')
 p=db.query(Payment).filter_by(rental_id=rid).first()
 if not p:db.rollback();raise HTTPException(400,'Missing payment record')
 r.asset_id=asset_id;r.status='active';r.id_checked=True;r.verified_by=o.id;r.issued_at=now();r.due_at=r.issued_at+timedelta(minutes=r.rate.minutes);r.condition_out='Good (operator verified)'
 p.status='verified';p.verified_at=now();p.operator_id=o.id;p.reference=reference[:100]
 if dep>0:db.add(Deposit(rental_id=rid,amount=dep,status='held',operator_id=o.id))
 logged_event(db,rid,'issued',o.id,f'Physical ID checked, {p.method} payment confirmed. Asset {asset_id}.');db.commit();flash(req,'Rental issued; due time recorded.');return go(f'/operator/rentals/{rid}')
@app.post('/operator/rentals/{rid}/return')
def return_item(req:Request,rid:int,condition:str=Form(...),action:str=Form(...),notes:str=Form(''),csrf:str=Form(...),db:Session=Depends(db_dep)):
 o=admin(req,db);check_csrf(req,csrf);r=db.get(Rental,rid)
 if not r or r.status not in ('active','overdue') or not r.asset:raise HTTPException(409,'No active issued item')
 if action not in ('available','maintenance','damaged'):raise HTTPException(400,'Invalid return disposition')
 r.status='completed';r.returned_at=now();r.condition_in=condition[:120];r.return_note=notes[:400];r.asset.status=action;r.asset.condition=condition[:90]
 db.add(Inspection(asset_id=r.asset_id,rental_id=rid,condition=condition[:100],action=f'Returned to {action}. {notes[:180]}',operator_id=o.id));logged_event(db,rid,'returned',o.id,f'Asset {r.asset.code}; {action}; {notes[:250]}');db.commit();flash(req,'Return recorded. Check refundable deposit status.');return go(f'/operator/rentals/{rid}')
@app.post('/operator/rentals/{rid}/deposit-release')
def release(req:Request,rid:int,csrf:str=Form(...),db:Session=Depends(db_dep)):
 o=admin(req,db);check_csrf(req,csrf);r=db.get(Rental,rid);d=db.query(Deposit).filter_by(rental_id=rid).first()
 if not r or r.status!='completed' or not d or d.status!='held':raise HTTPException(409,'Deposit is not releasable')
 d.status='released';d.released_at=now();d.operator_id=o.id;logged_event(db,rid,'deposit_released',o.id,str(d.amount));db.commit();flash(req,'Deposit recorded as released. Complete the actual cash/wallet refund separately.');return go(f'/operator/rentals/{rid}')
@app.post('/operator/rentals/{rid}/extension')
def extend(req:Request,rid:int,minutes:int=Form(...),reason:str=Form(...),csrf:str=Form(...),db:Session=Depends(db_dep)):
 o=admin(req,db);check_csrf(req,csrf);r=db.get(Rental,rid)
 if not r or r.status not in ('active','overdue') or minutes<=0 or minutes>1440:raise HTTPException(400,'Invalid extension')
 # Extensions are operator-reviewed; no automatic charge, as source does not define extension fees.
 r.due_at=r.due_at+timedelta(minutes=minutes);r.status='active' if now()<=r.due_at+timedelta(minutes=15) else 'overdue';logged_event(db,rid,'extension_approved',o.id,f'{minutes} minutes. {reason[:250]}');db.commit();flash(req,'Extension recorded. No additional unapproved fee was applied.');return go(f'/operator/rentals/{rid}')
@app.post('/operator/rentals/{rid}/event')
def event_submit(req:Request,rid:int,kind:str=Form(...),notes:str=Form(...),csrf:str=Form(...),db:Session=Depends(db_dep)):
 o=admin(req,db);check_csrf(req,csrf)
 if not db.get(Rental,rid) or kind not in ('reminder_sent','due_notice_sent','overdue_warning_sent','dispute_resolved','fault_checked'):raise HTTPException(400)
 logged_event(db,rid,kind,o.id,notes[:500]);db.commit();flash(req,'Operational event recorded.');return go(f'/operator/rentals/{rid}')
@app.post('/operator/rentals/{rid}/approval-request')
def approval_request(req:Request,rid:int,kind:str=Form(...),reason:str=Form(...),csrf:str=Form(...),db:Session=Depends(db_dep)):
 o=admin(req,db);check_csrf(req,csrf)
 if not db.get(Rental,rid) or kind not in ('fee_waiver','deposit_forfeiture','escalation','pricing_exception'):raise HTTPException(400)
 db.add(Approval(rental_id=rid,type=kind,reason=reason[:500],requested_by=o.id));db.commit();flash(req,'Approval request recorded for another authorized operator.');return go(f'/operator/rentals/{rid}')
@app.post('/operator/approvals/{aid}')
def approve(req:Request,aid:int,decision:str=Form(...),csrf:str=Form(...),db:Session=Depends(db_dep)):
 o=admin(req,db);check_csrf(req,csrf);a=db.get(Approval,aid)
 if not a or a.status!='pending' or decision not in ('approved','rejected'):raise HTTPException(409,'Invalid approval')
 if a.requested_by==o.id:raise HTTPException(403,'Second operator approval required')
 a.status=decision;a.decided_by=o.id;a.decided_at=now();logged_event(db,a.rental_id,'approval_'+decision,o.id,a.type);db.commit();flash(req,'Decision recorded. Approval does not automatically charge or forfeit funds.');return go(f'/operator/rentals/{a.rental_id}')
@app.get('/operator/finance')
def finance(req:Request,db:Session=Depends(db_dep)):
 op=admin(req,db);payments=db.query(Payment).order_by(Payment.id.desc()).limit(100).all();expenses=db.query(Expense).order_by(Expense.id.desc()).limit(100).all();deposits=db.query(Deposit).order_by(Deposit.id.desc()).all()
 earned=Decimal(db.query(func.coalesce(func.sum(Payment.amount),0)).filter_by(status='verified').scalar());costs=Decimal(db.query(func.coalesce(func.sum(Expense.amount),0)).scalar());held=Decimal(db.query(func.coalesce(func.sum(Deposit.amount),0)).filter_by(status='held').scalar())
 return html(req,'finance.html',op=op,payments=payments,expenses=expenses,deposits=deposits,earned=earned,costs=costs,held=held,flash=pull_flash(req),page='finance')
@app.post('/operator/finance/expenses')
def expense_submit(req:Request,category:str=Form(...),amount:str=Form(...),description:str=Form(''),csrf:str=Form(...),db:Session=Depends(db_dep)):
 o=admin(req,db);check_csrf(req,csrf)
 try:amt=Decimal(amount)
 except:raise HTTPException(400)
 if amt<=0 or amt>1000000:raise HTTPException(400)
 db.add(Expense(category=category[:70],amount=amt,description=description[:240],operator_id=o.id));db.commit();flash(req,'Operating expense recorded.');return go('/operator/finance')
@app.get('/operator/checks')
def checks(req:Request,db:Session=Depends(db_dep)):
 op=admin(req,db);return html(req,'checks.html',op=op,checks=db.query(Check).order_by(Check.id.desc()).limit(60).all(),assets=db.query(Asset).order_by(Asset.id.desc()).limit(15).all(),flash=pull_flash(req),page='checks')
@app.post('/operator/checks')
def check_submit(req:Request,kind:str=Form(...),stock_ok:str=Form(''),power_ok:str=Form(''),qr_ok:str=Form(''),cash_ok:str=Form(''),notes:str=Form(''),csrf:str=Form(...),db:Session=Depends(db_dep)):
 o=admin(req,db);check_csrf(req,csrf)
 if kind not in ('opening','closing'):raise HTTPException(400)
 db.add(Check(kind=kind,stock_ok=stock_ok=='yes',power_ok=power_ok=='yes',qr_ok=qr_ok=='yes',cash_ok=cash_ok=='yes',notes=notes[:500],operator_id=o.id));db.commit();flash(req,'Daily checklist saved.');return go('/operator/checks')
@app.get('/operator/reminders')
def reminders(req:Request,db:Session=Depends(db_dep)):
 op=admin(req,db);update_due(db);rentals=db.query(Rental).filter(Rental.status.in_(['active','overdue'])).order_by(Rental.due_at).all();due=now();rows=[]
 for r in rentals:
  past={e.type for e in db.query(Event).filter_by(rental_id=r.id).all()}
  if r.status=='overdue' and 'overdue_warning_sent' not in past:action='Overdue warning'
  elif due>=r.due_at and 'due_notice_sent' not in past:action='Due-time notice'
  elif due>=r.due_at-timedelta(minutes=30) and 'reminder_sent' not in past:action='30-minute reminder'
  else:action='Not yet due'
  rows.append((r,action))
 return html(req,'reminders.html',op=op,rows=rows,flash=pull_flash(req),page='reminders')
@app.get('/operator/export/rentals')
def export_rentals(req:Request,db:Session=Depends(db_dep)):
 admin(req,db);f=io.StringIO();w=csv.writer(f);w.writerow(['Rental ID','Student enrollment','Category','Asset','Status','Amount PKR','Created UTC','Issued UTC','Due UTC','Returned UTC'])
 for r in db.query(Rental).order_by(Rental.id).all():w.writerow([r.id,r.student.enrollment,r.category.name,r.asset.code if r.asset else '',r.status,str(r.amount),r.created_at,r.issued_at,r.due_at,r.returned_at])
 return StreamingResponse(iter([f.getvalue()]),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="srs_rental_records.csv"'})

@app.get('/health')
def health(db:Session=Depends(db_dep)):return {'status':'ok','categories':db.query(Category).count(),'assets':db.query(Asset).count()}

def create_operator(username,password,title='Authorized Operator'):
 if len(password)<12:raise ValueError('Password must be at least 12 characters')
 initdb()
 with SessionLocal() as db:
  o=db.query(Operator).filter_by(username=username).first()
  if o:raise ValueError('Operator username exists')
  db.add(Operator(username=username,password_hash=pw_hash(password),title=title));db.commit()

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--create-operator',action='store_true');parser.add_argument('--username');parser.add_argument('--password');parser.add_argument('--title',default='Authorized Operator');args=parser.parse_args()
 if args.create_operator:
  import getpass
  create_operator(args.username or input('Username: ').strip(),args.password or getpass.getpass('Password (12+ chars): '),args.title)
  print('Operator created')
 else:
  import uvicorn
  uvicorn.run('app:app',host='127.0.0.1',port=8000,reload=False)
