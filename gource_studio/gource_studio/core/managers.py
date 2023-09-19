from django.db import models
from django.db.models import Prefetch, Q


class ProjectQuerySet(models.QuerySet):
    # QuerySet filter to filter projects query using `User` instance.
    # - Helps easily filter our public/private projects
    def filter_permissions(self, actor):
        if actor is None or actor.is_superuser:
            return self # No-op

        if not actor.is_authenticated:
            # AnonymousUser - Only public projects
            return self.filter(is_public=True)
        else:
            # Normal User - Must be public project or creator/project member
            return self.filter(
                Q(is_public=True)
                |
                Q(Q(created_by=actor)|Q(members__user=actor)|Q(member_groups__group__user=actor))
            ).distinct()

    def with_latest_build(self):
        """
        Cache 'builds' prefetch with latest build available first
        """
        from .models import ProjectBuild
        return self.prefetch_related(
            Prefetch('builds', to_attr='_cached_latest_build',
                     queryset=ProjectBuild.objects.exclude(content='').order_by('-created_at'))
        )


class ProjectManager(models.Manager):
    def get_queryset(self):
        return ProjectQuerySet(model=self.model, using=self._db)
