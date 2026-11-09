ErrandGo - backend step 1: register and login

Setup
  python -m venv venv
  venv\Scripts\activate          (Windows)   |   source venv/bin/activate   (Mac/Linux)
  pip install -r requirements.txt
  copy .env.example .env         (then edit SECRET_KEY)
  python run.py

Open http://127.0.0.1:5000

Tests
  pip install pytest
  pytest -q
