from datetime import datetime, timedelta
import os

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.utils import timezone
import pytest

from gource_studio.core.models import (
    Project,
    ProjectCaption,
    ProjectOption,
)

TEST_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS_PATH = os.path.join(TEST_ROOT, "assets")


@pytest.mark.django_db
class TestProjectsAPI:

    def test_general_api_access(self, client):
        assert Project.objects.count() == 0

        req = client.get('/api/v1/')
        assert req.status_code == 200

        req = client.get('/api/v1/projects/')
        assert req.status_code == 200
        assert len(req.data['results']) == 0

        req = client.get('/api/v1/builds/')
        assert req.status_code == 200
        assert len(req.data['results']) == 0

        req = client.get('/api/v1/avatars/')
        assert req.status_code == 200
        assert len(req.data['results']) == 0
