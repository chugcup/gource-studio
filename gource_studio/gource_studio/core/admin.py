from django.contrib import admin

from .models import Project, ProjectMember

# Register your models here.
@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    pass


@admin.register(ProjectMember)
class ProjectMemberAdmin(admin.ModelAdmin):
    pass
