"""Seed a demo founder for first-run / smoke testing. Idempotent.

Run inside the stack:
    docker compose -f docker-compose.prod.yml exec -T backend python seed.py
"""
import logging
from database import SessionLocal, init_db
from schema import Founder

logging.basicConfig(level=logging.INFO)
FOUNDER_ID = "demo-founder"


def main():
    init_db()
    db = SessionLocal()
    try:
        existing = db.query(Founder).filter(Founder.id == FOUNDER_ID).first()
        if existing:
            print(f"founder '{FOUNDER_ID}' already exists")
            return
        db.add(Founder(id=FOUNDER_ID, email="demo@founder.test"))
        db.commit()
        print(f"created founder '{FOUNDER_ID}'")
    finally:
        db.close()


if __name__ == "__main__":
    main()
