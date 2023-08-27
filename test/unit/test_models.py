from django.core.exceptions import ValidationError
import pytest

from gource_studio.core.models import Project


@pytest.mark.django_db
class TestProjects:

    def test_project_model_basic(self):
        assert Project.objects.count() == 0

        project = Project.objects.create(name="test")
        assert Project.objects.count() == 1
        # Check some model defaults
        assert project.project_url_active is False
        assert project.project_branch == "master"
        assert project.project_vcs == "git"
        assert project.project_slug is None

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

