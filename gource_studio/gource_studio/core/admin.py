from django.contrib import admin

from .models import Project, ProjectMember, ProjectMemberGroup

# Register your models here.
@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    pass


@admin.register(ProjectMember)
class ProjectMemberAdmin(admin.ModelAdmin):
    pass


@admin.register(ProjectMemberGroup)
class ProjectMemberGroupAdmin(admin.ModelAdmin):
    pass
