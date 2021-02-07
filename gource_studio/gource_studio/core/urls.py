from django.urls import path, re_path

from . import views

urlpatterns = [
    re_path(r'^$', views.index, name='index'),
    re_path(r'^avatars/?$', views.avatars, name='avatars'),
    re_path(r'^avatars/upload/?$', views.avatar_upload, name='avatar-upload'),
    #re_path(r'^avatars/(?P<avatar_id>\d+)/$', views.avatar_details, name='avatar-details'),
    re_path(r'^avatars/(?P<avatar_id>\d+)/image/?$', views.avatar_image, name='avatar-image'),
    re_path(r'^projects/?$', views.projects, name='projects'),
    # - By ID
    re_path(r'^projects/(?P<project_id>\d+)/?$', views.project_details, name='project-details'),
    re_path(r'^projects/(?P<project_id>\d+)/avatars/?$', views.project_avatars, name='project-avatars'),
    #re_path(r'^projects/(?P<project_id>\d+)/avatars/(?P<avatar_id>\d+)/?$', views.project_avatar_details, name='project-avatar-details'),
    re_path(r'^projects/(?P<project_id>\d+)/avatars/upload/?$', views.project_avatar_upload, name='project-avatar-upload'),
    re_path(r'^projects/(?P<project_id>\d+)/avatars/(?P<avatar_id>\d+)/image/?$', views.project_avatar_image, name='project-avatar-image'),
    re_path(r'^projects/(?P<project_id>\d+)/audio/upload/?$', views.project_audio_upload, name='project-audio-upload'),
    re_path(r'^projects/(?P<project_id>\d+)/builds/?$', views.project_builds, name='project-builds'),
    re_path(r'^projects/(?P<project_id>\d+)/builds/(?P<build_id>\d+)/?$', views.project_build_details, name='project-build-details'),
    re_path(r'^projects/(?P<project_id>\d+)/builds/(?P<build_id>\d+)/screenshot.jpg$', views.project_build_screenshot, name='project-build-screenshot'),
    re_path(r'^projects/(?P<project_id>\d+)/builds/(?P<build_id>\d+)/thumbnail.jpg$', views.project_build_thumbnail, name='project-build-thumbnail'),
    re_path(r'^projects/(?P<project_id>\d+)/builds/(?P<build_id>\d+)/video.mp4$', views.project_build_video, name='project-build-video'),
    # - By slug
    re_path(r'^projects/(?P<project_slug>[-\w]+)/?$', views.project_details, name='project-details'),
    re_path(r'^projects/(?P<project_slug>[-\w]+)/avatars/?$', views.project_avatars, name='project-avatars'),
    re_path(r'^projects/(?P<project_slug>[-\w]+)/builds/?$', views.project_builds, name='project-builds'),
    re_path(r'^projects/(?P<project_slug>[-\w]+)/builds/(?P<build_id>\d+)/?$', views.project_build_details, name='project-build-details'),
    re_path(r'^projects/(?P<project_slug>[-\w]+)/builds/(?P<build_id>\d+)/screenshot.jpg$', views.project_build_screenshot, name='project-build-screenshot'),
    re_path(r'^projects/(?P<project_slug>[-\w]+)/builds/(?P<build_id>\d+)/thumbnail.jpg$', views.project_build_thumbnail, name='project-build-thumbnail'),
    re_path(r'^projects/(?P<project_slug>[-\w]+)/builds/(?P<build_id>\d+)/video.mp4$', views.project_build_video, name='project-build-video'),
    re_path(r'^new/?$', views.new_project, name='new-project'),
    re_path(r'^queue/?$', views.build_queue, name='build-queue'),
    re_path(r'^about/?$', views.about, name='about'),
    # Test views
    re_path(r'^test/log/?', views.fetch_log, name='test-fetch-log'),
    re_path(r'^test/queue/?', views.queue_video, name='test-queue-video'),
    re_path(r'^test/video/?', views.make_video, name='test-make-video'),
    re_path(r'^test/?', views.index, name='test-home'),
]
