from datetime import datetime, timedelta
import json
import os
from pprint import pprint
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.utils import timezone
import pytest

from gource_studio.core.constants import PROJECT_OPTION_DEFAULTS
from gource_studio.core.models import (
    Project,
    ProjectCaption,
    ProjectOption,
)

TEST_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS_PATH = os.path.join(TEST_ROOT, "assets")

# Some tests compare option counts, so make this constant easily accessible
DEFAULT_OPTIONS_COUNT = len(PROJECT_OPTION_DEFAULTS)

# Mock functions
def _pass(*args, **kwargs):
    return True

def _fake_download_git_log(project_url, branch="master"):
    log_data = "1296068768|cameronmcefee|A|/README\n" \
               "1315975361|Johnneylee Jack Rollins|M|/README"
    log_hash = "7fd1a60b01f91b314f59955a4e4d4e80d8edf11d"
    log_subject = "Merge pull request #6 from Spaceghost/patch-1"
    tags_list = [
        [timezone.make_aware(datetime(2011,1,26,19,6,8)), "1.0.0"]
    ]
    return log_data, log_hash, log_subject, tags_list


@pytest.mark.django_db
class TestProjectsAPI:

    def _create_user(self, username, password=None):
        # Helper to create new User account
        # - NOTE: 'password' defaults to username if omitted
        User = get_user_model()
        new_user = User.objects.create(username=username)
        new_user.set_password(password if password else username)
        new_user.save()
        return new_user

    def test_general_api_access(self, client):
        assert Project.objects.count() == 0

        req = client.get('/api/v1/')
        assert req.status_code == 200

        # FIXME: unordered object_list warning
        req = client.get('/api/v1/projects/')
        assert req.status_code == 200
        assert len(req.data['results']) == 0

        req = client.get('/api/v1/builds/')
        assert req.status_code == 200
        assert len(req.data['results']) == 0

        req = client.get('/api/v1/avatars/')
        assert req.status_code == 200
        assert len(req.data['results']) == 0

    def test_create_project_api(self, client):
        assert Project.objects.count() == 0

        # Verify that an unauthenticated client cannot create Projects
        post_data = {
            "name": "test minimal",
            "project_vcs": "git",
            "project_branch": "master",
        }
        req = client.post('/api/v1/projects/', post_data)
        assert req.status_code == 403

        # Authenticate
        self._create_user("user1", password="pass1")
        client.login(username="user1", password="pass1")

        # Test creating a new Project via the API
        post_data = {
            "name": "test minimal",
            "project_vcs": "git",
            "project_branch": "master",
        }
        # Create using the minimal options
        req = client.post('/api/v1/projects/', post_data)
        assert req.status_code == 201
        assert req.data['project_log']['url'] is None  # No log data

        # Test creating project with "remote" download
        with patch('gource_studio.core.api.views.validate_project_url', _pass):
            with patch('gource_studio.core.api.views.test_http_url', _pass):
                with patch('gource_studio.core.api.views.download_git_log', _fake_download_git_log):
                    post_data['project_url'] = 'http://example.com'
                    post_data['project_url_active'] = True
                    post_data['load_captions_from_tags'] = True
                    req = client.post('/api/v1/projects/', post_data)
                    assert req.status_code == 201
                    # - Check log data loaded
                    assert req.data['project_log'] is not None
                    assert req.data['project_log']['commit_time'] is not None
                    assert req.data['project_log']['commit_hash'] is not None
                    assert req.data['project_log']['commit_preview'] is not None

        # Invalid options
        # - No name
        req = client.post('/api/v1/projects/', {"name": "", "project_vcs": "git", "project_branch": "master"})
        assert req.status_code == 400
        # - Bad VCS
        req = client.post('/api/v1/projects/', {"name": "test", "project_vcs": "foo", "project_branch": "master"})
        assert req.status_code == 400
        # - No branch
        req = client.post('/api/v1/projects/', {"name": "test", "project_vcs": "hg", "project_branch": ""})
        assert req.status_code == 400

    def test_edit_project_api(self, client):
        # Create a user (and owner)
        user1 = self._create_user("user1", password="pass1")
        client.login(username="user1", password="pass1")

        project = Project.objects.create(name="test", project_vcs="git",
                                         project_slug="test", created_by=user1)

        # Fetch contents of Project
        req = client.get(f'/api/v1/projects/{project.id}/')
        assert req.status_code == 200
        assert req.data['id'] == project.id
        assert req.data['project_slug'] == "test"

        # Verify we can request using the `project_slug` in place of PK
        #req = client.get('/api/v1/projects/test/')
        #assert req.status_code == 200
        #assert req.data['id'] == project.id
        # - Check HTML view
        req = client.get('/projects/test/')
        assert req.status_code == 200

        # Change the project_slug
        post_data = {
            "project_slug": "test2"
        }
        req = client.patch(f'/api/v1/projects/{project.id}/', json.dumps(post_data), content_type="application/json")
        assert req.status_code == 200
        assert req.data['project_slug'] == "test2"

        # Request using the new `project_slug`
        #req = client.get('/api/v1/projects/test2/')
        #assert req.status_code == 200
        #assert req.data['id'] == project.id
        # - Check HTML view
        req = client.get('/projects/test2/')
        assert req.status_code == 200

    def test_edit_project_options_api(self, client):
        # Create a user (and owner)
        user1 = self._create_user("user1", password="pass1")
        client.login(username="user1", password="pass1")

        project = Project.objects.create(name="test", project_vcs="git",
                                         project_slug="test", created_by=user1)

        # Fetch contents of Project
        req = client.get(f'/api/v1/projects/{project.id}/')
        assert req.status_code == 200
        assert req.data['id'] == project.id
        req = client.get(f'/api/v1/projects/{project.id}/options/')
        assert req.status_code == 200
        assert len(req.data) > 0
        assert len(req.data) == DEFAULT_OPTIONS_COUNT   # Preloaded options

        # Set some options
        post_data = {
            "gource_options": {
                "seconds-per-day": "2",
                "auto-skip-seconds": "0.2",
            },
            "sync_gource_options": True,
        }
        req = client.patch(f'/api/v1/projects/{project.id}/', json.dumps(post_data), content_type="application/json")
        assert req.status_code == 200
        req = client.get(f'/api/v1/projects/{project.id}/options/')
        assert req.status_code == 200
        assert req.data == [
            {"name": "auto-skip-seconds", "value": "0.2", "value_type": "float"},
            {"name": "seconds-per-day", "value": "2", "value_type": "float"},
        ]

        # Send additional option and verify it is added to current set
        post_data = {
            "gource_options": {
                "caption-size": 40,
            },
        }
        req = client.patch(f'/api/v1/projects/{project.id}/', json.dumps(post_data), content_type="application/json")
        assert req.status_code == 200
        req = client.get(f'/api/v1/projects/{project.id}/options/')
        assert req.status_code == 200
        assert req.data == [
            {"name": "auto-skip-seconds", "value": "0.2", "value_type": "float"},
            {"name": "caption-size", "value": "40", "value_type": "int"},
            {"name": "seconds-per-day", "value": "2", "value_type": "float"},
        ]

        # Verify using flag we can sync settings (so all options to be sent together)
        post_data = {
            "gource_options": {
                "seconds-per-day": "1",
            },
            "sync_gource_options": True,
        }
        req = client.patch(f'/api/v1/projects/{project.id}/', json.dumps(post_data), content_type="application/json")
        assert req.status_code == 200
        req = client.get(f'/api/v1/projects/{project.id}/options/')
        assert req.status_code == 200
        assert req.data == [
            {"name": "seconds-per-day", "value": "1", "value_type": "float"},
        ]

        # Error validation
        # - Invalid option value
        post_data["gource_options"] = {"seconds-per-day": "foo"}
        req = client.patch(f'/api/v1/projects/{project.id}/', json.dumps(post_data), content_type="application/json")
        assert req.status_code == 400
        # - Invalid option name
        post_data["gource_options"] = {"foo": "bar"}
        req = client.patch(f'/api/v1/projects/{project.id}/', json.dumps(post_data), content_type="application/json")
        assert req.status_code == 400
        # - Invalid option format
        post_data["gource_options"] = [{"foo": "bar"}]
        req = client.patch(f'/api/v1/projects/{project.id}/', json.dumps(post_data), content_type="application/json")
        assert req.status_code == 400

    def test_project_members_api(self, client):
        # Create a user (and owner)
        user1 = self._create_user("user1", password="pass1")
        client.login(username="user1", password="pass1")

        # Create a private project
        project = Project.objects.create(name="test", project_vcs="git", project_slug="test",
                                         created_by=user1, is_public=False)

        # Fetch contents of Project
        req = client.get(f'/api/v1/projects/{project.id}/')
        assert req.status_code == 200
        assert req.data['id'] == project.id
        # Verify our user is the Project owner
        assert req.data['created_by'] == {'id': user1.id, 'username': user1.username}

        # Fetch list of members (should be empty)
        req = client.get(f'/api/v1/projects/{project.id}/members/')
        assert req.status_code == 200
        assert req.data == []   # Empty

        # Create additional users; add them to project
        user2 = self._create_user("user2", password="pass")
        user3 = self._create_user("user3", password="pass")
        user4 = self._create_user("user4", password="pass")

        # Verify each member cannot view private project
        client.logout()
        for username in [
            user2.username,
            user3.username,
            user4.username,
        ]:
            client.login(username=username, password="pass")
            req = client.get(f'/api/v1/projects/{project.id}/')
            assert req.status_code == 404
            client.logout()
        client.login(username="user1", password="pass1")

        # Add each user to project (with different roles)
        for username, role in [
            (user2.username, 'viewer'),
            (user3.username, 'developer'),
            (user4.username, 'maintainer'),
        ]:
            post_data = {
                'username': username,
                'role': role,
            }
            req = client.post(f'/api/v1/projects/{project.id}/members/', json.dumps(post_data), content_type="application/json")
            assert req.status_code == 201

        # Fetch list of members
        req = client.get(f'/api/v1/projects/{project.id}/members/')
        assert req.status_code == 200
        assert len(req.data) == 3
        user2_member = [r for r in req.data if r['user']['username'] == user2.username][0]

        # Verify each member can now view project
        client.logout()
        for username in [
            user2.username,
            user3.username,
            user4.username,
        ]:
            client.login(username=username, password="pass")
            req = client.get(f'/api/v1/projects/{project.id}/')
            assert req.status_code == 200
            client.logout()
        client.login(username="user1", password="pass1")

        # Change role for user
        assert user2_member['role'] == 'viewer'
        patch_data = {'role': 'maintainer'}
        req = client.patch(f'/api/v1/projects/{project.id}/members/{user2.id}/', json.dumps(patch_data), content_type="application/json")
        assert req.status_code == 200
        assert req.data['role'] == 'maintainer'
        user2_member = req.data

        # Delete user
        req = client.delete(f'/api/v1/projects/{project.id}/members/{user2.id}/')
        assert req.status_code == 204
        # Fetch list of members
        req = client.get(f'/api/v1/projects/{project.id}/members/')
        assert req.status_code == 200
        assert len(req.data) == 2
        assert user2.username not in [r['user']['username'] for r in req.data]

        # Input validation
        # - Verify incorrect 'role' option
        post_data = {'username': user2.username, 'role': 'foo'}
        req = client.post(f'/api/v1/projects/{project.id}/members/', json.dumps(post_data), content_type="application/json")
        assert req.status_code == 400
        assert 'Invalid role' in str(req.data)
        patch_data = {'role': 'foo'}
        req = client.patch(f'/api/v1/projects/{project.id}/members/{user3.id}/', json.dumps(patch_data), content_type="application/json")
        assert req.status_code == 400
        assert 'not a valid choice' in str(req.data)
        # - User already assigned
        post_data = {'username': user3.username, 'role': 'viewer'}
        req = client.post(f'/api/v1/projects/{project.id}/members/', json.dumps(post_data), content_type="application/json")
        assert req.status_code == 400
        assert 'already assigned' in str(req.data)
        # - Missing 'username'/'role' fields
        post_data = {'username': user2.username}
        req = client.post(f'/api/v1/projects/{project.id}/members/', json.dumps(post_data), content_type="application/json")
        assert req.status_code == 400
        assert 'Missing required field' in str(req.data)
        post_data = {'role': 'viewer'}
        req = client.post(f'/api/v1/projects/{project.id}/members/', json.dumps(post_data), content_type="application/json")
        assert req.status_code == 400
        assert 'Missing required field' in str(req.data)
        # - Invalid user
        post_data = {'username': 'user5', 'role': 'viewer'}
        req = client.post(f'/api/v1/projects/{project.id}/members/', json.dumps(post_data), content_type="application/json")
        assert req.status_code == 400
        assert 'Invalid username' in str(req.data)
