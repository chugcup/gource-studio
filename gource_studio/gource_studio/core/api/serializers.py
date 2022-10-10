from rest_framework.reverse import reverse
from rest_framework import serializers

from ..models import (
    Project,
    ProjectBuild,
    ProjectBuildOption,
    ProjectCaption,
    ProjectOption,
    ProjectMember,
    ProjectUserAvatar,
    ProjectUserAvatarAlias,
    UserAvatar,
    UserAvatarAlias,
    UserPlaylist,
    UserPlaylistProject,
)


class ProjectLogSerializer(serializers.Serializer):
    """Serializes `project_log_*` fields to separate object"""
    url = serializers.SerializerMethodField()
    updated_at = serializers.DateTimeField(source='project_log_updated_at', allow_null=True)
    commit_time = serializers.DateTimeField(source='project_log_commit_time', allow_null=True)
    commit_hash = serializers.CharField(source='project_log_commit_hash', allow_null=True)
    commit_preview = serializers.CharField(source='project_log_commit_preview', allow_null=True)

    def get_url(self, obj):
        if obj.project_log:
            return reverse('api-project-log-download', args=[obj.pk], request=self.context.get('request'))
        return None

    class Meta:
        model = Project
        fields = ('commit_hash', 'commit_preview', 'commit_time', 'updated_at', 'url')


class ProjectMemberSerializer(serializers.HyperlinkedModelSerializer):
    project = serializers.SerializerMethodField('get_project_url')
    project_id = serializers.PrimaryKeyRelatedField(source='project', read_only=True)
    user = serializers.SerializerMethodField()
    date_added = serializers.DateTimeField(read_only=True)
    added_by = serializers.SerializerMethodField()

    def get_project_url(self, obj):
        return reverse('api-project-detail', args=[obj.project_id], request=self.context.get('request'))

    def get_user(self, obj):
        return {
            "id": obj.user.id,
            "username": obj.user.username
        }

    def get_added_by(self, obj):
        if obj.added_by is None:
            return None
        return {
            "id": obj.added_by.id,
            "username": obj.added_by.username
        }

    class Meta:
        model = ProjectMember
        fields = ('project', 'project_id', 'user', 'role',
                  'date_added', 'added_by')



class ProjectSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.SerializerMethodField()
    project_log = ProjectLogSerializer(source='*')
    options = serializers.SerializerMethodField('get_options_url')
    builds = serializers.SerializerMethodField('get_builds_url')
    avatars = serializers.SerializerMethodField('get_avatars_url')
    captions = serializers.SerializerMethodField('get_captions_url')
    members = serializers.SerializerMethodField('get_members_url')
    build_audio = serializers.SerializerMethodField('get_build_audio_url')

    def get_url(self, obj):
        return reverse('api-project-detail', args=[obj.pk], request=self.context.get('request'))

    def get_options_url(self, obj):
        return reverse('api-project-options-list', args=[obj.pk], request=self.context.get('request'))

    def get_builds_url(self, obj):
        return reverse('api-project-builds-byproject-list', args=[obj.pk], request=self.context.get('request'))

    def get_avatars_url(self, obj):
        return reverse('api-project-useravatars-list', args=[obj.pk], request=self.context.get('request'))

    def get_captions_url(self, obj):
        return reverse('api-project-captions-list', args=[obj.pk], request=self.context.get('request'))

    def get_members_url(self, obj):
        return reverse('api-project-members-list', args=[obj.pk], request=self.context.get('request'))

    def get_build_audio_url(self, obj):
        if obj.build_audio:
            return reverse('api-project-build-audio-download', args=[obj.pk], request=self.context.get('request'))
        return None

    class Meta:
        model = Project
        fields = ('id', 'name', 'project_slug', 'project_url', 'project_url_active',
                  'project_branch', 'project_vcs',
                  'project_log', 'build_title', 'build_logo', 'video_size',
                  'build_audio', 'build_audio_name',
                  'options', 'builds', 'captions', 'avatars', 'members',
                  'is_public', 'is_project_changed', 'created_at', 'updated_at', 'url')
        read_only_fields = ('project_log', 'created_at', 'updated_at')


class ProjectBuildSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.SerializerMethodField()
    project_log = serializers.SerializerMethodField('get_project_log_url')
    options = serializers.SerializerMethodField('get_options_url')
    content = serializers.SerializerMethodField('get_content_url')
    #content_size = serializers.IntegerField(source='size', allow_null=True)
    content_size = serializers.IntegerField(allow_null=True)
    screenshot = serializers.SerializerMethodField('get_screenshot_url')
    thumbnail = serializers.SerializerMethodField('get_thumbnail_url')

    def get_url(self, obj):
        return reverse('api-project-build-detail', args=[obj.project_id, obj.pk], request=self.context.get('request'))

    def get_project_log_url(self, obj):
        if obj.project_log:
            return reverse('api-project-build-project-log-download', args=[obj.project_id, obj.pk], request=self.context.get('request'))
        return None

    def get_content_url(self, obj):
        if obj.content:
            return reverse('api-project-build-content-download', args=[obj.project_id, obj.pk], request=self.context.get('request'))
        return None

    def get_screenshot_url(self, obj):
        if obj.screenshot:
            return reverse('api-project-build-screenshot-download', args=[obj.project_id, obj.pk], request=self.context.get('request'))
        return None

    def get_thumbnail_url(self, obj):
        if obj.thumbnail:
            return reverse('api-project-build-thumbnail-download', args=[obj.project_id, obj.pk], request=self.context.get('request'))
        return None

    def get_options_url(self, obj):
        return reverse('api-project-build-options-list', args=[obj.project_id, obj.pk], request=self.context.get('request'))

    class Meta:
        model = ProjectBuild
        fields = ('id', 'project_id', 'project_branch',
                  'status', 'error_description', 'content', 'content_size', 'duration',
                  'screenshot', 'thumbnail', 'project_log', 'options',
                  'queued_at', 'running_at', 'aborted_at', 'completed_at', 'errored_at', 'url')
        read_only_fields = ('project_id', 'project_branch', 'status', 'content_size', 'duration',
                            'queued_at', 'running_at', 'aborted_at', 'completed_at', 'errored_at')


class ProjectOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectOption
        fields = ('name', 'value', 'value_type')


class ProjectBuildOptionSerializer(ProjectOptionSerializer):
    class Meta:
        model = ProjectBuildOption
        fields = ('name', 'value', 'value_type')


class ProjectCaptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectCaption
        fields = ('timestamp', 'text')


class UserAvatarAliasSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserAvatarAlias
        fields = ('name',)
        read_only_fields = ('name',)


class ProjectUserAvatarAliasSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectUserAvatarAlias
        fields = ('name',)
        read_only_fields = ('name',)


class UserAvatarSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField('get_image_url')
    aliases = UserAvatarAliasSerializer(many=True)

    def get_image_url(self, obj):
        if obj.image:
            return reverse('api-useravatar-image-download', args=[obj.pk], request=self.context.get('request'))
        return None

    class Meta:
        model = UserAvatar
        fields = ('name', 'image', 'aliases')
        read_only_fields = ('name',)


class ProjectUserAvatarSerializer(UserAvatarSerializer):
    aliases = ProjectUserAvatarAliasSerializer(many=True)

    def get_image_url(self, obj):
        if obj.image:
            return reverse('api-project-useravatar-image-download', args=[obj.project_id, obj.pk], request=self.context.get('request'))
        return None

    class Meta:
        model = ProjectUserAvatar
        fields = ('name', 'image', 'aliases')
        read_only_fields = ('name',)


class UserPlaylistSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.SerializerMethodField()
    projects = serializers.SerializerMethodField('get_projects_url')
    projects_count = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)

    def get_url(self, obj):
        return reverse('api-user-playlist-detail', args=[obj.pk], request=self.context.get('request'))

    def get_projects_url(self, obj):
        return reverse('api-user-playlist-projects-list', args=[obj.pk], request=self.context.get('request'))

    def get_projects_count(self, obj):
        return obj.projects.count()

    class Meta:
        model = UserPlaylist
        fields = ('id', 'name', 'projects', 'projects_count', 'created_at', 'updated_at', 'url')


class UserPlaylistProjectSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.SerializerMethodField()
    #playlist = serializers.SerializerMethodField('get_playlist_url')
    playlist_id = serializers.PrimaryKeyRelatedField(source='playlist', read_only=True)
    name = serializers.CharField(source='project.name', read_only=True)
    project = serializers.SerializerMethodField('get_project_url')
    project_id = serializers.PrimaryKeyRelatedField(source='project', read_only=True)
    screenshot_url = serializers.SerializerMethodField()
    content_url = serializers.SerializerMethodField()

    def get_url(self, obj):
        return reverse('api-user-playlist-project-detail', args=[obj.playlist_id, obj.pk], request=self.context.get('request'))

    def get_playlist_url(self, obj):
        return reverse('api-user-playlist-detail', args=[obj.playlist_id], request=self.context.get('request'))

    def get_project_url(self, obj):
        return reverse('api-project-detail', args=[obj.project_id], request=self.context.get('request'))

    def get_content_url(self, obj):
        return reverse('project-latest-build-video', args=[obj.project_id], request=self.context.get('request'))

    def get_screenshot_url(self, obj):
        return reverse('project-latest-build-screenshot', args=[obj.project_id], request=self.context.get('request'))

    class Meta:
        model = UserPlaylistProject
        fields = ('id', 'playlist_id', 'project', 'project_id', 'name', 'index', 'content_url', 'screenshot_url', 'url')
