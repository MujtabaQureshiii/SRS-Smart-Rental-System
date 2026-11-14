"""Optional live SMS reminder sender. Requires Twilio SMS credentials and student consent.
Run periodically (e.g. once per 5 minutes) using OS Task Scheduler or cron.
Without configured credentials, no message will be sent or marked as sent.
"""
import os,base64,urllib.request,urllib.parse
from datetime import timedelta
from sqlalchemy import select
from app import SessionLocal,Rental,Student,Event,initdb,now,logged_event

def send_sms(phone,message):
 sid=os.environ.get('TWILIO_ACCOUNT_SID');token=os.environ.get('TWILIO_AUTH_TOKEN');from_number=os.environ.get('TWILIO_FROM_NUMBER')
 if not all((sid,token,from_number)):
  print('SKIPPED: Twilio SMS credentials are not configured.');return False
 if not phone.startswith('+'):
  print('SKIPPED: Student phone must use E.164 international format, e.g. +92...');return False
 params=urllib.parse.urlencode({'To':phone,'From':from_number,'Body':message}).encode()
 req=urllib.request.Request(f'https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json',data=params,method='POST')
 req.add_header('Authorization','Basic '+base64.b64encode(f'{sid}:{token}'.encode()).decode())
 req.add_header('Content-Type','application/x-www-form-urlencoded')
 try:
  with urllib.request.urlopen(req,timeout=12) as response:return response.status in (200,201)
 except Exception as exc:print(f'Provider request failed: {type(exc).__name__}: {exc}');return False

def run():
 initdb();time=now();sent=0
 with SessionLocal() as db:
  rentals=db.query(Rental).filter(Rental.status.in_(['active','overdue'])).all()
  for r in rentals:
   if not r.due_at or not r.student.phone:continue
   recorded={e.type for e in db.query(Event).filter_by(rental_id=r.id).all()}
   if time>r.due_at+timedelta(minutes=15):typ='overdue_warning_sent';message=f'SRS: Rental #{r.id} is overdue. Please return your {r.category.name} to the campus station.'
   elif time>=r.due_at:typ='due_notice_sent';message=f'SRS: Rental #{r.id} is due now. Please return your {r.category.name} to the campus station.'
   elif time>=r.due_at-timedelta(minutes=30):typ='reminder_sent';message=f'SRS reminder: {r.category.name} rental #{r.id} is due at {r.due_at:%H:%M} (campus local time).'
   else:continue
   if typ in recorded:continue
   if send_sms(r.student.phone,message):
    logged_event(db,r.id,typ,notes='SMS accepted by configured provider');db.commit();sent+=1
 print(f'Completed: {sent} reminders submitted. Delivery to handset is not guaranteed by API acceptance.')
if __name__=='__main__':run()
