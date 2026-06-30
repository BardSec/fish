import os
import tempfile

import pytest

from app import create_app
from config import Config
from prisma.seed import seed


@pytest.fixture()
def app():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    class TestConfig(Config):
        TESTING = True
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{path}"
        UPLOAD_FOLDER = tempfile.mkdtemp()

    app = create_app(TestConfig)
    with app.app_context():
        seed()
    yield app
    os.remove(path)


@pytest.fixture()
def client(app):
    return app.test_client()
