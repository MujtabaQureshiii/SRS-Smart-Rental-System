import os
from pathlib import Path
if __name__=='__main__':
 import uvicorn
 print('SRS: http://127.0.0.1:8000 | Operator: http://127.0.0.1:8000/operator/login')
 uvicorn.run('app:app',host=os.getenv('SRS_HOST','127.0.0.1'),port=int(os.getenv('SRS_PORT','8000')))
