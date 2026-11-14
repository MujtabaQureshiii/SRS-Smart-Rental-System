"""Download open-licensed Wikimedia Commons product photographs for offline SRS demo.
Run on a PC with internet: python download_product_photos.py
See PHOTO_CREDITS.md for links, authors, and license terms.
"""
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import quote
from PIL import Image
from io import BytesIO

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'static'/'photos';OUT.mkdir(parents=True,exist_ok=True)
FILES={
 'basic-calculator':'Simple_Calculator.jpg',
 'scientific-calculator':'Scientific_calculator_casio.jpg',
 'usb-drive':'USB_Flash_Drives.jpg',
 'power-bank':'Portable_power_bank.jpg',
 'charger-cable-set':'MobileUsbCharger.jpg',
 'umbrella':'Black_umbrella.jpg',
}

def main():
 total=0
 for slug,filename in FILES.items():
  dest=OUT/(slug+'.jpg')
  if dest.exists() and dest.stat().st_size>5000:
   print(f'Already downloaded: {slug}');total+=1;continue
  url='https://commons.wikimedia.org/wiki/Special:FilePath/'+quote(filename)+'?width=640'
  try:
   request=Request(url,headers={'User-Agent':'SRS-University-Demonstration/1.0 (educational website; contact: local project)'})
   with urlopen(request,timeout=15) as response: data=response.read(8_000_000)
   image=Image.open(BytesIO(data)).convert('RGB');image.thumbnail((850,850))
   image.save(dest,'JPEG',quality=86,optimize=True)
   print(f'Downloaded: {slug} ({dest.stat().st_size//1024} KB)')
   total+=1
  except Exception as exc:print(f'Could not download {slug}: {exc}. The web application will try the online photograph and then an icon fallback.')
 print(f'{total}/{len(FILES)} images available offline.')

if __name__=='__main__':main()
