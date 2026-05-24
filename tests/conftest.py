import os

from hypothesis import settings


settings.register_profile("helios", deadline=None)
settings.load_profile("helios")


def pytest_sessionstart(session):
    # Force deterministic test isolation from local real-service credentials.
    os.environ["HELIOS_LLM_API_KEY"] = ""
    os.environ["OPENAI_API_KEY"] = ""
    os.environ["HELIOS_QQ_APP_ID"] = ""
    os.environ["HELIOS_QQ_CLIENT_SECRET"] = ""
    os.environ["HELIOS_QQ_SANDBOX"] = "1"
