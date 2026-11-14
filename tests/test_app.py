"""Functional end-to-end tests using a temporary SQLite database."""
import os,sys,pytest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
os.environ['DATABASE_URL']='sqlite:///'+str(ROOT/'tests'/'test_srs.sqlite')
os.environ['SRS_SECRET_KEY']='test-secret-key-123456789'
from fastapi.testclient import TestClient
import app as srs

@pytest.fixture
def client():
 srs.Base.metadata.drop_all(srs.engine)
 with TestClient(srs.app) as c:
  yield c

def csrf(response):
 from html.parser import HTMLParser
 class Parser(HTMLParser):
  value=None
  def handle_starttag(self,tag,attrs):
   attrs=dict(attrs)
   if tag=='input' and attrs.get('name')=='csrf':self.value=attrs.get('value')
 p=Parser();p.feed(response.text);assert p.value;return p.value

def make_admin():

 with srs.SessionLocal() as db: existing={x.username for x in db.query(srs.Operator).all()}
 if 'operator1' not in existing:srs.create_operator('operator1','ExampleSecurePass!123')
 if 'operator2' not in existing:srs.create_operator('operator2','AnotherExamplePass!123')

def admin_login(client,who='operator1',pw='ExampleSecurePass!123'):
 t=csrf(client.get('/operator/login'))
 r=client.post('/operator/login',data={'username':who,'password':pw,'csrf':t},follow_redirects=True)
 assert r.status_code==200 and 'Admin Dashboard' in r.text
 return csrf(client.get("/operator/login"))

def enroll(client, verify=True):
 # An actual station QR points at the signed station entry URL.
 scanned=client.get('/station/'+srs.station_token(),follow_redirects=True)
 assert scanned.status_code==200 and 'Student Registration' in scanned.text
 t=csrf(client.get('/'))
 r=client.post('/register',data={'csrf':t,'name':'Test Student','enrollment':'24K-0535','department':'Computer Science','email':'','phone':''},follow_redirects=True)
 assert r.status_code==200 and 'Identity Verification' in r.text
 if verify:
  with srs.SessionLocal() as db:
   stu=db.query(srs.Student).filter_by(enrollment='24K-0535').one();sid=stu.id
   has_operator=db.query(srs.Operator).count()>0
  if not has_operator:
   srs.create_operator('operator1','ExampleSecurePass!123')
  with TestClient(srs.app) as opclient:
   t=admin_login(opclient)
   resp=opclient.post(f'/operator/students/{sid}/verify',data={'csrf':t},follow_redirects=True)
   assert resp.status_code==200 and 'Verified' in resp.text
  assert 'Select item' in client.get('/items').text
 return csrf(client.get('/operator/login'))

def request_rental(client):
 with srs.SessionLocal() as db:
  c=db.query(srs.Category).filter_by(name='Power Bank').one();rate=db.query(srs.Rate).filter_by(category_id=c.id,label='3-hour session').one();cid=c.id;rid=rate.id
 t=enroll(client)
 r=client.post('/rentals/request',data={'csrf':t,'category_id':cid,'rate_id':rid,'method':'cash'},follow_redirects=False)
 assert r.status_code==303
 token=r.headers['location'].split('/')[-1]
 with srs.SessionLocal() as db:r=db.query(srs.Rental).filter_by(token=token).one();return r.id,token

def test_seed_and_pages(client):
 assert client.get('/health').json()=={'status':'ok','categories':6,'assets':22}
 assert client.get('/').status_code==200
 assert client.get('/items').status_code==200
 assert client.get('/operator/station-qr').status_code==401
 assert 'PKR 380' in client.get('/items').text
 assert client.get('/operator').status_code==401

def test_student_and_operator_complete_rental(client):
 make_admin();rid,token=request_rental(client)
 assert 'awaiting operator' in client.get('/rental/'+token).text.lower()
 with srs.SessionLocal() as db:
  r=db.get(srs.Rental,rid);cid=r.category_id;aid=db.query(srs.Asset).filter_by(category_id=cid,status='available').first().id
 t=admin_login(client)
 bad=client.post(f'/operator/rentals/{rid}/issue',data={'csrf':t,'asset_id':aid,'id_checked':'yes','payment_verified':'no','deposit_amount':'500'},follow_redirects=False)
 assert bad.status_code==400
 ok=client.post(f'/operator/rentals/{rid}/issue',data={'csrf':t,'asset_id':aid,'id_checked':'yes','payment_verified':'yes','deposit_amount':'500','reference':'receipt001'},follow_redirects=True)
 assert ok.status_code==200
 with srs.SessionLocal() as db:
  r=db.get(srs.Rental,rid);assert r.status=='active' and r.due_at>r.issued_at
  assert db.get(srs.Asset,aid).status=='rented'
  assert db.query(srs.Payment).filter_by(rental_id=rid).one().status=='verified'
 double=client.post(f'/operator/rentals/{rid}/issue',data={'csrf':t,'asset_id':aid,'id_checked':'yes','payment_verified':'yes','deposit_amount':'0'},follow_redirects=False)
 assert double.status_code==409
 returned=client.post(f'/operator/rentals/{rid}/return',data={'csrf':t,'condition':'Good','action':'maintenance','notes':'Recharge battery'},follow_redirects=True)
 assert returned.status_code==200
 with srs.SessionLocal() as db:
  assert db.get(srs.Asset,aid).status=='maintenance';assert db.get(srs.Rental,rid).status=='completed'
 released=client.post(f'/operator/rentals/{rid}/deposit-release',data={'csrf':t},follow_redirects=True)
 assert released.status_code==200
 with srs.SessionLocal() as db:assert db.query(srs.Deposit).filter_by(rental_id=rid).one().status=='released'
 assert client.get('/operator/finance').status_code==200
 assert '380' in client.get('/operator/finance').text

def test_student_cannot_access_admin_and_wrong_csrf(client):
 assert client.post('/register',data={'csrf':'bad','name':'A','enrollment':'12','department':'CS'}).status_code==403
 t=enroll(client)
 assert client.get('/operator/inventory').status_code==401
 assert client.get('/operator/rentals').status_code==401
 assert client.post('/operator/checks',data={'csrf':t,'kind':'opening'}).status_code==401

def test_other_student_cannot_read_rental(client):
 rid,token=request_rental(client)
 t=csrf(client.get('/'))
 response=client.post('/register',data={'csrf':t,'name':'Another Student','enrollment':'24K-1111','department':'Computer Science'},follow_redirects=True)
 assert response.status_code==200
 assert client.get('/rental/'+token).status_code==403

def test_double_approval_and_finance_and_inventory(client):
 make_admin();rid,token=request_rental(client)
 t=admin_login(client)
 a=client.post(f'/operator/rentals/{rid}/approval-request',data={'csrf':t,'kind':'escalation','reason':'Overdue as documented'},follow_redirects=True)
 assert a.status_code==200
 with srs.SessionLocal() as db:aid=db.query(srs.Approval).one().id
 assert client.post(f'/operator/approvals/{aid}',data={'csrf':t,'decision':'approved'}).status_code==403
 assert client.post('/operator/finance/expenses',data={'csrf':t,'category':'Cleaning','amount':'150','description':'Wipes'},follow_redirects=True).status_code==200
 assert client.post('/operator/checks',data={'csrf':t,'kind':'opening','stock_ok':'yes','power_ok':'yes','qr_ok':'yes','cash_ok':'yes','notes':'ok'},follow_redirects=True).status_code==200
 assert client.get('/operator/export/rentals').headers['content-type'].startswith('text/csv')
 assert client.post('/operator/logout',data={'csrf':t},follow_redirects=False).status_code==303
 t=admin_login(client,'operator2','AnotherExamplePass!123')
 assert client.post(f'/operator/approvals/{aid}',data={'csrf':t,'decision':'approved'},follow_redirects=True).status_code==200
 with srs.SessionLocal() as db:assert db.get(srs.Approval,aid).status=='approved'

def test_due_rule(client):
 make_admin();rid,token=request_rental(client)
 with srs.SessionLocal() as db:
  r=db.get(srs.Rental,rid);a=db.query(srs.Asset).filter_by(category_id=r.category_id).first();aid=a.id
 t=admin_login(client)
 client.post(f'/operator/rentals/{rid}/issue',data={'csrf':t,'asset_id':aid,'id_checked':'yes','payment_verified':'yes','deposit_amount':'0'},follow_redirects=True)
 with srs.SessionLocal() as db:
  r=db.get(srs.Rental,rid);r.due_at=srs.now()-srs.timedelta(minutes=16);db.commit()
 assert client.get('/operator/reminders').status_code==200
 with srs.SessionLocal() as db:assert db.get(srs.Rental,rid).status=='overdue'


def test_operator_login_audit(client):
 make_admin()
 t=csrf(client.get('/operator/login'))
 failed=client.post('/operator/login',data={'csrf':t,'username':'operator1','password':'wrong'},follow_redirects=True)
 assert failed.status_code==200
 assert 'Incorrect username' in failed.text
 t=admin_login(client)
 page=client.get('/operator/access')
 assert page.status_code==200 and 'Operator Access Log' in page.text
 assert 'Failed' in page.text and 'Success' in page.text
 with srs.SessionLocal() as db:assert db.query(srs.LoginAudit).count()==2

# Cork visual refresh preserves existing rentals, adds station QR and verification before item selection.
def test_cork_shared_theme_and_all_operator_pages(client):
    assert client.get('/static/css/style.css').status_code == 200
    theme = client.get('/static/css/cork.css')
    assert theme.status_code == 200
    assert 'cork-products' in theme.text and '--bg:#f3f4fb' in theme.text
    assert client.get('/static/img/srs-mark.svg').status_code == 200
    assert client.get('/static/img/icons.svg').status_code == 200
    for path in ['/', '/items', '/operator/login']:
        response = client.get(path)
        assert response.status_code == 200, path
        assert 'cork.css?v=3' in response.text
        assert 'student-mode' in response.text
    make_admin()
    admin_login(client)
    for path in ['/operator', '/operator/station-qr', '/operator/access', '/operator/students',
                 '/operator/inventory', '/operator/rentals', '/operator/reminders',
                 '/operator/finance', '/operator/checks']:
        response = client.get(path)
        assert response.status_code == 200, path
        assert 'cork.css?v=3' in response.text
        assert 'operator-mode' in response.text
        assert '/static/img/icons.svg#dashboard' in response.text
    dashboard = client.get('/operator').text
    assert 'Rental Activity' in dashboard
    assert 'Inventory Status' in dashboard
    assert '22' in dashboard
    assert '0 rental requests in this period' in dashboard


def test_cork_dashboard_uses_actual_rental_data(client):
    rid, token = request_rental(client)
    make_admin()
    admin_login(client)
    dashboard = client.get('/operator').text
    assert '1 rental request in this period' in dashboard
    assert 'Pending rental requests' in dashboard
    assert '/operator/rentals?status=pending' in dashboard
    assert 'Admin Dashboard' in dashboard


def test_qr_scan_and_verification_required(client):
 # Registration is refused until a real station-code URL has been opened.
 t=csrf(client.get('/operator/login'))
 assert client.post('/register',data={'csrf':t,'name':'A','enrollment':'A1','department':'CS'}).status_code==403
 assert client.get('/station/invalid-code').status_code==404
 client.get('/station/'+srs.station_token())
 t=csrf(client.get('/'))
 r=client.post('/register',data={'csrf':t,'name':'Student B','enrollment':'ST-2026','department':'CS'},follow_redirects=True)
 assert r.status_code==200 and 'Waiting for operator verification' in r.text
 with srs.SessionLocal() as db:
  cat=db.query(srs.Category).filter_by(name='Power Bank').first()
  rate=db.query(srs.Rate).filter_by(category_id=cat.id).first()
  sid=db.query(srs.Student).filter_by(enrollment='ST-2026').one().id
 assert client.get(f'/select/{cat.id}',follow_redirects=False).headers['location']=='/verification'
 bad=client.post('/rentals/request',data={'csrf':t,'category_id':cat.id,'rate_id':rate.id,'method':'cash'})
 assert bad.status_code==403
 srs.create_operator('operator1','ExampleSecurePass!123')
 with TestClient(srs.app) as op:
  admin_login(op)
  qr=op.get('/operator/station-qr/image.png')
  assert qr.status_code==200 and qr.headers['content-type']=='image/png' and qr.content.startswith(b'\x89PNG')
  op.post(f'/operator/students/{sid}/verify',data={'csrf':csrf(op.get('/operator/login'))})
 assert client.get(f'/select/{cat.id}').status_code==200
 assert client.post('/rentals/request',data={'csrf':t,'category_id':cat.id,'rate_id':rate.id,'method':'cash'},follow_redirects=False).status_code==303
