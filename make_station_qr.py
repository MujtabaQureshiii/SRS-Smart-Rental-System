"""Optional command-line SRS station QR. Prefer /operator/station-qr UI."""
import sys
from pathlib import Path
import qrcode
from urllib.parse import urlsplit

root=Path(__file__).resolve().parent
code_file=root/'.srs_station_token'
if not code_file.exists():
 import secrets
 code_file.write_text(secrets.token_urlsafe(24))
origin=(sys.argv[1] if len(sys.argv)>1 else 'http://127.0.0.1:8000').rstrip('/')
parsed=urlsplit(origin)
if parsed.scheme not in ('http','https') or not parsed.hostname:raise SystemExit('Provide a valid site base URL')
url=origin+'/station/'+code_file.read_text().strip()
output=root/'srs_station_qr.png'
qr=qrcode.QRCode(box_size=12,border=4,error_correction=qrcode.constants.ERROR_CORRECT_H)
qr.add_data(url);qr.make(fit=True)
qr.make_image(fill_color='#172747',back_color='white').save(output)
print('SRS station QR:',output,'\nScan URL:',url)
print('NOTE: 127.0.0.1 works only on the same computer. Use the server LAN IP to scan on phones.')
