"""Headless static CSS render of server-generated pages; no local browser HTTP navigation."""
import os,sys,re,asyncio
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['DATABASE_URL']='sqlite:///'+str(ROOT/'docs'/'visual_test.sqlite')
os.environ['SRS_SECRET_KEY']='visual-demo-secret-do-not-deploy'
sys.path.insert(0,str(ROOT))
from fastapi.testclient import TestClient
import app as srs
from playwright.async_api import async_playwright
srs.Base.metadata.drop_all(srs.engine)
from html.parser import HTMLParser
class CSRF(HTMLParser):
 def __init__(self):super().__init__();self.value=None
 def handle_starttag(self,t,a):
  a=dict(a)
  if t=='input' and a.get('name')=='csrf':self.value=a.get('value')
def csrf(html):p=CSRF();p.feed(html);return p.value
pages={}
with TestClient(srs.app) as student:
 pages['login']=student.get('/operator/login').text
 student.get('/station/'+srs.station_token())
 student.post('/register',data={'csrf':csrf(student.get('/').text),'name':'Demo Student','enrollment':'DEMO001','department':'Computing'},follow_redirects=True)
 with srs.SessionLocal() as db:stu=db.query(srs.Student).filter_by(enrollment='DEMO001').one();sid=stu.id
 srs.create_operator('demooperator','DemoPassword1234!')
 with TestClient(srs.app) as op:
  op.post('/operator/login',data={'csrf':csrf(op.get('/operator/login').text),'username':'demooperator','password':'DemoPassword1234!'},follow_redirects=True)
  pages['dashboard']=op.get('/operator').text
  op.post(f'/operator/students/{sid}/verify',data={'csrf':csrf(op.get('/operator/login').text)})
 pages['items']=student.get('/items').text
css='\n'.join((ROOT/'static/css'/f).read_text() for f in ['style.css','option2.css','cork.css'])
# External images omitted in this CSS-only rendering, real client loads them when online.
for key,val in pages.items():
 val=re.sub(r'<link rel="stylesheet" href="/static/css/[^\"]+">','',val)
 val=val.replace('</head>','<style>'+css+'</style></head>')
 val=val.replace('<script src="/static/js/app.js?v=cork" defer></script>','')
 pages[key]=val
async def main():
 async with async_playwright() as p:
  browser=await p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
  for size in [(1440,900),(390,844)]:
   page=await browser.new_page(viewport={'width':size[0],'height':size[1]})
   for label,markup in pages.items():
    await page.set_content(markup,wait_until='domcontentloaded');await page.wait_for_timeout(750);await page.evaluate("document.querySelectorAll('.cork-photo-wrap img[data-remote]').forEach(i=>i.style.display='none')");await page.screenshot(path=str(ROOT/'docs'/f'preview_{label}_{size[0]}.png'),full_page=True)
    out=await page.evaluate('({scroll:document.documentElement.scrollWidth,inner:window.innerWidth})')
    print(label,size[0],out)
   await page.close()
  await browser.close()
asyncio.run(main())
