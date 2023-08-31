from datetime import datetime, timedelta
import os

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.test import override_settings
from django.utils import timezone
import pytest

from gource_studio.core.utils import (
    analyze_gource_log,
    estimate_gource_video_duration,
    get_executable_path,
    get_ffmpeg,
    get_ffmpeg_version,
    get_ffplay,
    get_ffprobe,
    get_git,
    get_git_version,
    get_gource,
    get_gource_version,
    get_mercurial,
    get_mercurial_version,
    get_xvfb_run,
    validate_project_url,
)

TEST_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS_PATH = os.path.join(TEST_ROOT, "assets")


def test_get_executable_path():
    # Check for command that should exist
    assert get_executable_path("dir")
    # Check for command that definitely shouldn't exist
    with pytest.raises(RuntimeError):
        get_executable_path("asdfasdfasdfasdf")
    # By giving it a `settings` name, we can make it available
    with override_settings(**{"FAKE_PATH": "/bin/asdf"}):
        assert get_executable_path("asdfasdfasdfasdf", "FAKE_PATH") == "/bin/asdf"


def test_known_app_paths():
    with override_settings(**{"FFMPEG_PATH": "/bin/asdf"}):
        assert get_ffmpeg() == "/bin/asdf"
    with override_settings(**{"FFPLAY_PATH": "/bin/asdf"}):
        assert get_ffplay() == "/bin/asdf"
    with override_settings(**{"FFPROBE_PATH": "/bin/asdf"}):
        assert get_ffprobe() == "/bin/asdf"
    with override_settings(**{"GIT_PATH": "/bin/asdf"}):
        assert get_git() == "/bin/asdf"
    with override_settings(**{"GOURCE_PATH": "/bin/asdf"}):
        assert get_gource() == "/bin/asdf"
    with override_settings(**{"MERCURIAL_PATH": "/bin/asdf"}):
        assert get_mercurial() == "/bin/asdf"
    with override_settings(**{"XVFB_RUN_PATH": "/bin/asdf"}):
        assert get_xvfb_run() == "/bin/asdf"


def test_get_software_versions():
    # - git
    assert isinstance(get_git_version(), str)
    assert all(isinstance(n, int) for n in get_git_version(split=True))
    # - hg
    assert isinstance(get_mercurial_version(), str)
    assert all(isinstance(n, int) for n in get_mercurial_version(split=True))
    # - ffmpeg
    assert isinstance(get_ffmpeg_version(), str)
    assert all(isinstance(n, int) for n in get_ffmpeg_version(split=True))


@override_settings(**{"PROJECT_DOMAINS": ["github.com"]})
def test_validate_project_url():
    # Validation (no error, no response)
    assert validate_project_url("http://github.com") is None
    assert validate_project_url("https://github.com") is None

    with pytest.raises(ValueError):
        # Subdomains don't count
        validate_project_url("https://test.github.com") is None
    with pytest.raises(ValueError):
        # Invalid domain
        validate_project_url("https://example.com")
    with pytest.raises(ValueError):
        # http[s] only
        validate_project_url("ftp://github.com")
    with pytest.raises(ValueError):
        validate_project_url("foo")
    with pytest.raises(TypeError):
        validate_project_url(9999)


def test_analyze_gource_log():
    # Use static project log from test assets
    sample_log = os.path.join(ASSETS_PATH, "Hello-World", "Hello-World.log")
    with open(sample_log, 'r') as f:
        data = f.read()

    # Known project log properties
    assert analyze_gource_log(data) == {
        'start_date': datetime(2011, 1, 26, 19, 6, 8),
        'end_date': datetime(2011, 9, 14, 4, 42, 41),
        'num_changes': 2,
        'num_commits': 2,
        'num_commit_days': 2,
        'users': ['cameronmcefee', 'Johnneylee Jack Rollins']
    }


def test_estimate_gource_video_duration():
    # Use static project log from test assets
    sample_log = os.path.join(ASSETS_PATH, "Hello-World", "Hello-World.log")
    with open(sample_log, 'r') as f:
        data = f.read()

    assert estimate_gource_video_duration(data) == 12.0
    assert estimate_gource_video_duration(data, {"seconds-per-day": 2.0}) == 14.0


