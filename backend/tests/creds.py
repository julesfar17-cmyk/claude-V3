"""Identifiants de test chargés depuis backend/.env — jamais en dur dans le code."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

DEMO_EMAIL = os.environ["TEST_DEMO_EMAIL"]
DEMO_PASSWORD = os.environ["TEST_DEMO_PASSWORD"]
ADMIN_EMAIL = os.environ["TEST_ADMIN_EMAIL"]
ADMIN_PASSWORD = os.environ["TEST_ADMIN_PASSWORD"]
VIP_EMAIL = os.environ["TEST_VIP_EMAIL"]
VIP_PASSWORD = os.environ["TEST_VIP_PASSWORD"]
