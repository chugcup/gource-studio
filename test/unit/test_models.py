from datetime import datetime, timedelta
import os

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.utils import timezone
import pytest

from gource_studio.core.constants import PROJECT_OPTION_DEFAULTS
from gource_studio.core.models import (
    Project,
    ProjectCaption,
    ProjectOption,
    ProjectUserAvatar,
    ProjectUserAvatarAlias,
    UserAvatar,
    UserAvatarAlias,
)

TEST_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS_PATH = os.path.join(TEST_ROOT, "assets")

# Some tests compare option counts, so make this constant easily accessible
DEFAULT_OPTIONS_COUNT = len(PROJECT_OPTION_DEFAULTS)


@pytest.mark.django_db
class TestProjects:

    def _add_sample_log(self, model):
        # - Use static project log from test assets
        sample_log = os.path.join(ASSETS_PATH, "Hello-World", "Hello-World.log")
        # - For completeness, fill out commit info cache
        model.project_log_commit_hash = "7fd1a60b01f91b314f59955a4e4d4e80d8edf11d"
        model.project_log_commit_time = timezone.make_aware(datetime(2012, 3, 6, 15, 6, 50))
        model.project_log_commit_preview = "Merge pull request #6 from Spaceghost/patch-1"
        model.project_log_updated_at = timezone.now()
        with open(sample_log, 'r') as f:
            model.project_log.save('gource.log', ContentFile(f.read()))

    def _add_avatar_image(self, model, image_path):
        with open(image_path, 'rb') as f:
            model.image.save(os.path.basename(image_path), ContentFile(f.read()))

    def test_project_model_basic(self):
        assert Project.objects.count() == 0

        project = Project.objects.create(name="test")
        assert Project.objects.count() == 1
        # Check some model defaults
        assert str(project) == "test"
        assert project.project_url_active is False
        assert project.project_branch == "master"
        assert project.project_vcs == "git"
        assert project.project_slug is None
        assert project.get_absolute_url() is not None
        # - No builds yet
        assert project.latest_build is None
        assert project.has_build_waiting is False
        # - No log file
        with pytest.raises(RuntimeError):
            project.analyze_log()
        # - No captions
        assert project.generate_captions_file() is None

        # - Toggle project "dirty" state
        assert project.is_project_changed is False
        project.set_project_changed(True)
        assert project.is_project_changed is True
        project.set_project_changed(True)
        assert project.is_project_changed is True # No change
        project.set_project_changed(False)
        assert project.is_project_changed is False

    def test_project_slug(self):
        # Slug is used as a (unique) alias to project in URLs, etc.
        project = Project.objects.create(name="test")
        assert project.project_slug is None

        # - Verify we cannot set slug to all numbers
        with pytest.raises(ValidationError):
            project.project_slug = "12345"
            project.save()
        # - Validated on creation as well
        with pytest.raises(ValidationError):
            Project.objects.create(name="test2", project_slug="12345")
        # - Verify that empty slug reverts to `None`
        project.project_slug = ""
        project.save()
        assert project.project_slug is None

        project.project_slug = "test"
        project.save()

        # Verify that slug is unique across projects
        with pytest.raises(ValidationError) as exc_info:
            Project.objects.create(name="test2", project_slug="test")
        assert "Project with this slug already exists" in str(exc_info.value)

    def test_project_log(self):
        # The project log is the Gource log format parsed from a VCS repo
        #   {timestamp}|{author}|{action}|{filepath}
        project = Project.objects.create(name="test")

        # Add a project log file
        self._add_sample_log(project)

        # Known project log properties
        assert project.analyze_log() == {
            'start_date': datetime(2011, 1, 26, 19, 6, 8),
            'end_date': datetime(2011, 9, 14, 4, 42, 41),
            'num_changes': 2,
            'num_commits': 2,
            'num_commit_days': 2,
            'users': ['cameronmcefee', 'Johnneylee Jack Rollins']
        }

    def test_project_options(self):
        # Project options generally map to Gource cmdline arguments
        #   --{name}={value}
        #
        # NOTE: Within the system, Gource options should be whitelisted to avoid
        #       situations where the Gource application could be run interactively.
        project = Project.objects.create(name="test")
        assert project.options.count() == DEFAULT_OPTIONS_COUNT

        # Add some options
        po1 = ProjectOption.objects.create(project=project, name='seconds-per-day', value='0.5', value_type='float')
        po2 = ProjectOption.objects.create(project=project, name='caption-size', value='20', value_type='int')

        assert project.options.count() == (2 + DEFAULT_OPTIONS_COUNT)
        # Check some basic model functions
        for po in (po1, po2):
            assert str(po) == f'{po.name}={po.value}'
            assert po.to_dict()['name'] == po.name

    def test_project_captions(self):
        # Caption is a format used by Gource to render title events
        #   {timestamp}|{caption}
        project = Project.objects.create(name="test")
        assert project.captions.count() == 0

        init_time = timezone.now()
        # Add some captions
        pc1 = ProjectCaption.objects.create(project=project, timestamp=init_time, text='Caption 1')
        pc2 = ProjectCaption.objects.create(project=project, timestamp=init_time+timedelta(hours=1), text='Caption 2')
        pc3 = ProjectCaption.objects.create(project=project, timestamp=init_time-timedelta(hours=1), text='Caption 3')

        assert project.captions.count() == 3
        # Check some basic model functions
        for pc in (pc1, pc2, pc3):
            assert str(pc) == pc.text
            assert pc.to_dict()['text'] == pc.text
            assert pc.to_text().endswith(f'|{pc.text}')  # {timestamp}|{text}

        # Ensure captions are returned in 'timestamp' order
        assert [pc.pk for pc in project.captions.all()] == [pc3.pk, pc1.pk, pc2.pk]

        # Generate the captions content (list of lines)
        sample_captions = project.generate_captions_file()
        assert sample_captions is not None
        assert len(sample_captions) == 3
        assert sample_captions[0].endswith('|Caption 3')

    def test_project_avatars(self):
        sample_avatar_blue = os.path.join(ASSETS_PATH, "avatar_blue.jpg")
        sample_avatar_ninja = os.path.join(ASSETS_PATH, "avatar_ninja.png")

        project = Project.objects.create(name="test")
        # Globals
        assert UserAvatar.objects.count() == 0
        assert UserAvatarAlias.objects.count() == 0
        # Per-project
        project.avatars.count() == 0
        ProjectUserAvatar.objects.count() == 0

        with pytest.raises(RuntimeError):
            project.resolve_avatars()       # No Gource log

        # Add a project log file
        self._add_sample_log(project)

        # No avatars yet
        assert project.resolve_avatars() == {}

        # Create global avatars
        # - First, test if the UserAvatar is missing the image file
        avatar1 = UserAvatar.objects.create(name='cameronmcefee')
        assert project.resolve_avatars() == {}
        # - Add proper image and check map
        self._add_avatar_image(avatar1, sample_avatar_blue)
        avatar_map = project.resolve_avatars()
        assert 'cameronmcefee' in avatar_map
        # - Add another global avatar and matching alias
        avatar2 = UserAvatar.objects.create(name='johnee')
        self._add_avatar_image(avatar2, sample_avatar_blue)
        alias2_1 = avatar2.add_alias(name='Johnneylee Jack Rollins')
        avatar_map = project.resolve_avatars()
        assert 'cameronmcefee' in avatar_map
        assert len(avatar_map['cameronmcefee']) == 3
        assert 'Johnneylee Jack Rollins' in avatar_map
        assert len(avatar_map['Johnneylee Jack Rollins']) == 3
        assert avatar_map['Johnneylee Jack Rollins'][1] == avatar2
        assert avatar_map['Johnneylee Jack Rollins'][2] == alias2_1
        # Verify that an 'UserAvatar' will overrule a 'UserAvatarAlias'
        avatar3 = UserAvatar.objects.create(name='Johnneylee Jack Rollins')
        self._add_avatar_image(avatar3, sample_avatar_blue)
        avatar_map = project.resolve_avatars()
        assert 'Johnneylee Jack Rollins' in avatar_map
        assert avatar_map['Johnneylee Jack Rollins'][1] == avatar3
        assert avatar_map['Johnneylee Jack Rollins'][2] is None

        # Create project avatars
        # - First, test if the UserAvatar is missing the image file
        p_avatar1 = ProjectUserAvatar.objects.create(project=project, name='cameronmcefee')
        avatar_map = project.resolve_avatars()
        assert 'cameronmcefee' in avatar_map
        assert avatar_map['cameronmcefee'][1] == avatar1    # Still using global
        # - Add proper image and check map
        self._add_avatar_image(p_avatar1, sample_avatar_ninja)
        avatar_map = project.resolve_avatars()
        assert 'cameronmcefee' in avatar_map
        assert avatar_map['cameronmcefee'][1] == p_avatar1
        # - Add another project avatar and matching alias
        p_avatar2 = ProjectUserAvatar.objects.create(project=project, name='johnee')
        self._add_avatar_image(p_avatar2, sample_avatar_ninja)
        p_alias2_1 = p_avatar2.add_alias(name='Johnneylee Jack Rollins')
        avatar_map = project.resolve_avatars()
        assert 'cameronmcefee' in avatar_map
        assert len(avatar_map['cameronmcefee']) == 3
        assert avatar_map['cameronmcefee'][1] == p_avatar1
        assert 'Johnneylee Jack Rollins' in avatar_map
        assert len(avatar_map['Johnneylee Jack Rollins']) == 3
        assert avatar_map['Johnneylee Jack Rollins'][1] == p_avatar2
        assert avatar_map['Johnneylee Jack Rollins'][2] == p_alias2_1
        # Verify that an 'ProjectUserAvatar' will overrule a 'ProjectUserAvatarAlias'
        p_avatar3 = ProjectUserAvatar.objects.create(project=project, name='Johnneylee Jack Rollins')
        self._add_avatar_image(p_avatar3, sample_avatar_ninja)
        avatar_map = project.resolve_avatars()
        assert 'Johnneylee Jack Rollins' in avatar_map
        assert avatar_map['Johnneylee Jack Rollins'][1] == p_avatar3
        assert avatar_map['Johnneylee Jack Rollins'][2] is None

    def test_create_project_build(self):
        # From a `Project` instance, create a new `ProjectBuild`
        # and verify settings/captions/etc. copied
        project = Project.objects.create(name="test", build_logo_resize=False, build_background_resize=False)

        # Without a `project_log`, verify creation fails
        with pytest.raises(RuntimeError):
            project.create_build(defer_queue=True)

        # Add some options
        po1 = ProjectOption.objects.create(project=project, name='seconds-per-day', value='0.5', value_type='float')
        po2 = ProjectOption.objects.create(project=project, name='caption-size', value='20', value_type='int')
        # Add a caption
        pc1 = ProjectCaption.objects.create(project=project, timestamp=timezone.now(), text='Caption 1')
        # Add a project log file
        # - Use static project log from test assets
        sample_log = os.path.join(ASSETS_PATH, "Hello-World", "Hello-World.log")
        # - For completeness, fill out commit info cache
        project.project_log_commit_hash = "7fd1a60b01f91b314f59955a4e4d4e80d8edf11d"
        project.project_log_commit_time = timezone.make_aware(datetime(2012, 3, 6, 15, 6, 50))
        project.project_log_commit_preview = "Merge pull request #6 from Spaceghost/patch-1"
        project.project_log_updated_at = timezone.now()
        with open(sample_log, 'r') as f:
            project.project_log.save('gource.log', ContentFile(f.read()))
        # Add an audio file
        sample_audio = os.path.join(ASSETS_PATH, "vivaldi-winter.mp3")
        with open(sample_log, 'rb') as f:
            project.build_audio.save('vivaldi-winter.mp3', ContentFile(f.read()))
        # Add a background and logo
        sample_background = os.path.join(ASSETS_PATH, "background.jpg")
        with open(sample_background, 'rb') as f:
            project.build_background.save('background.jpg', ContentFile(f.read()))
        sample_logo = os.path.join(ASSETS_PATH, "globe.png")
        with open(sample_logo, 'rb') as f:
            project.build_logo.save('globe.png', ContentFile(f.read()))

        assert project.builds.count() == 0

        # Create a new build from current project settings
        build1 = project.create_build(defer_queue=True)
        assert build1.status == "pending"
        assert build1.project_log.size == project.project_log.size
        assert build1.build_audio.size == project.build_audio.size
        assert build1.build_logo.size == project.build_logo.size
        assert build1.build_background.size == project.build_background.size
        assert build1.options.count() == (2 + DEFAULT_OPTIONS_COUNT)
        assert [str(opt) for opt in build1.options.all()] == \
               [str(opt) for opt in project.options.all()]
        assert build1.captions.count() == 1
        assert [str(cpt) for cpt in build1.captions.all()] == \
               [str(cpt) for cpt in project.captions.all()]
        assert project.builds.count() == 1
        # Create another new build and verify different from first
        build2 = project.create_build(defer_queue=True)
        assert build2.status == "pending"
        assert build2.project_log.size == project.project_log.size
        assert build1.pk != build2.pk
        assert project.builds.count() == 2

        # Test cloning a ProjectBuild from an existing one
        # - To verify it is using targeted build, modify Project
        # + Remove one option
        po2.delete()
        # + Add a caption
        pc2 = ProjectCaption.objects.create(project=project, timestamp=timezone.now()+timedelta(hours=1), text='Caption 2')

        # Clone the build
        build3 = build2.clone_build(defer_queue=True)
        assert build3.status == "pending"
        assert build3.project_log.size == build2.project_log.size
        assert build3.project_captions.size == build2.project_captions.size
        assert build3.pk != build2.pk
        # Check against source ProjectBuild
        assert build1.options.count() == (2 + DEFAULT_OPTIONS_COUNT) # Project has 1
        assert [str(opt) for opt in build2.options.all()] == \
               [str(opt) for opt in build3.options.all()]
        assert build1.captions.count() == 1 # Project has 2
        assert [str(cpt) for cpt in build2.captions.all()] == \
               [str(cpt) for cpt in build3.captions.all()]
        assert project.builds.count() == 3
