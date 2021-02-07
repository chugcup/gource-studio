from datetime import datetime
import logging
import os
import re
import ssl
import time
import urllib

from django import forms
from django.core.files import File
from django.core.files.base import ContentFile
from django.core.paginator import Paginator
from django.db.models import Exists, OuterRef
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.utils.timezone import make_aware, now as utc_now
from django.views.decorators.csrf import csrf_protect
from django.views.static import serve

# Ignore SSL verification
ssl._create_default_https_context = ssl._create_unverified_context

from .models import Project, ProjectBuild, ProjectUserAvatar, UserAvatar
from .tasks import generate_gource_build
from .utils import (
    analyze_gource_log,     #(data):
    download_git_log,       #(url, branch="master"):
    generate_gource_video,  #(log_data, seconds_per_day=0.1, framerate=60):
    get_video_duration,     #(video_path):
    get_video_thumbnail,    #(video_path, width=512, secs=None, percent=None):
    test_http_url,          #(url):
)


#############################################################################
##  Main Views
#############################################################################


def index(request):
    "Landing page"
    # Return latest 4 projects
    # - Subquery filter removes any projects without a successful build
    # TODO: sort by latest build
    context = {
        'projects': Project.objects.prefetch_related('builds')\
                                   .filter(
                                       Exists(ProjectBuild.objects.filter(project=OuterRef('pk'))\
                                                                  .exclude(content=''))
                                   )\
                                   .order_by('-id')[:8],
    }
    return render(request, 'core/index.html', context)


def projects(request):
    "Projects page"
    context = {
        'projects': Project.objects.prefetch_related('builds')\
                                             .order_by('-id'),
    }
    # Pagination
    paginator = Paginator(context['projects'], 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    context['page_obj'] = page_obj
    return render(request, 'core/projects.html', context)


def project_details(request, project_id=None, project_slug=None):
    "Project Details page"
    if project_id:
        project = get_object_or_404(Project, **{'id': project_id})
    elif project_slug:
        project = get_object_or_404(Project, **{'project_slug': project_slug})
    context = {
        'project': project,
        'build': project.latest_build
    }
    return render(request, 'core/project.html', context)


def project_builds(request, project_id=None, project_slug=None):
    "Project Builds page"
    if project_id:
        project = get_object_or_404(Project, **{'id': project_id})
    elif project_slug:
        project = get_object_or_404(Project, **{'project_slug': project_slug})
    context = {
        'project': project,
        'builds': ProjectBuild.objects.select_related('project')\
                                     .filter(project=project)\
                                     .order_by('-id'),
    }
    # Pagination
    paginator = Paginator(context['builds'], 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    context['page_obj'] = page_obj
    return render(request, 'core/project_builds.html', context)


@csrf_protect
def project_build_details(request, project_id=None, project_slug=None, build_id=None):
    "Project Build Details page"
    if project_id:
        project = get_object_or_404(Project, **{'id': project_id})
    elif project_slug:
        project = get_object_or_404(Project, **{'project_slug': project_slug})

    build = get_object_or_404(ProjectBuild, **{'project_id': project.id, 'id': build_id})

    if request.method == 'DELETE':
        # Delete build
        build.delete()
        return HttpResponseRedirect(f'/projects/{project.id}/')

    context = {
        'project': project,
        'build': build
    }
    return render(request, 'core/project.html', context)


def project_build_screenshot(request, project_id=None, project_slug=None, build_id=None):
    "Project Build screenshot"
    if project_id:
        project = get_object_or_404(Project, **{'id': project_id})
    elif project_slug:
        project = get_object_or_404(Project, **{'project_slug': project_slug})
    build = get_object_or_404(ProjectBuild, **{'project_id': project.id, 'id': build_id})
    filepath = build.screenshot.path
    return serve(request, os.path.basename(filepath), os.path.dirname(filepath))


def project_build_thumbnail(request, project_id=None, project_slug=None, build_id=None):
    "Project Build thumbnail"
    if project_id:
        project = get_object_or_404(Project, **{'id': project_id})
    elif project_slug:
        project = get_object_or_404(Project, **{'project_slug': project_slug})
    build = get_object_or_404(ProjectBuild, **{'project_id': project.id, 'id': build_id})
    filepath = build.thumbnail.path
    return serve(request, os.path.basename(filepath), os.path.dirname(filepath))


def project_build_video(request, project_id=None, project_slug=None, build_id=None):
    "Project Build video"
    if project_id:
        project = get_object_or_404(Project, **{'id': project_id})
    elif project_slug:
        project = get_object_or_404(Project, **{'project_slug': project_slug})
    build = get_object_or_404(ProjectBuild, **{'project_id': project.id, 'id': build_id})
    filepath = build.content.path
    return serve(request, os.path.basename(filepath), os.path.dirname(filepath))


def avatar_image(request, avatar_id):
    "Global avatar image"
    avatar = get_object_or_404(UserAvatar, **{'id': avatar_id})
    filepath = avatar.image.path
    return serve(request, os.path.basename(filepath), os.path.dirname(filepath))


def project_avatar_image(request, project_id=None, project_slug=None, avatar_id=None):
    "Project avatar image"
    if project_id:
        project = get_object_or_404(Project, **{'id': project_id})
    elif project_slug:
        project = get_object_or_404(Project, **{'project_slug': project_slug})
    avatar = get_object_or_404(ProjectUserAvatar, **{'project_id': project.id, 'id': avatar_id})
    filepath = avatar.image.path
    return serve(request, os.path.basename(filepath), os.path.dirname(filepath))


class UploadAvatarForm(forms.Form):
    name = forms.CharField(max_length=255)
    image = forms.ImageField()

@csrf_protect
def avatar_upload(request):
    "Upload a new avatar"
    if request.method == 'POST':
        form = UploadAvatarForm(request.POST, request.FILES)
        if form.is_valid():
            # TODO: Validate as .jpg or .png (or convert)
            # TODO: rescale to 256x256
            avatar = UserAvatar(
                name=request.POST['name'],
                image=request.FILES['image']
            )
            #avatar.created_by = request.user
            avatar.save()
            return HttpResponseRedirect('/avatars/')
        else:
            logging.error("Invalid form: %s", form.errors)
    return HttpResponseRedirect('/avatars/')


@csrf_protect
def project_avatar_upload(request, project_id=None, project_slug=None):
    "Upload a new project avatar"
    if project_id:
        project = get_object_or_404(Project, **{'id': project_id})
    elif project_slug:
        project = get_object_or_404(Project, **{'project_slug': project_slug})

    if request.method == 'POST':
        form = UploadAvatarForm(request.POST, request.FILES)
        if form.is_valid():
            # TODO: Validate as .jpg or .png (or convert)
            # TODO: rescale to 256x256
            avatar = ProjectUserAvatar(
                project=project,
                name=request.POST['name'],
                image=request.FILES['image']
            )
            #avatar.created_by = request.user
            avatar.save()
            return HttpResponseRedirect(f'/projects/{project.id}/avatars/')
        else:
            logging.error("Invalid form: %s", form.errors)
    return HttpResponseRedirect(f'/projects/{project.id}/avatars/')


class UploadAudioForm(forms.Form):
    build_audio = forms.FileField()

@csrf_protect
def project_audio_upload(request, project_id=None, project_slug=None):
    "Upload a new project audio file (MP3)"
    if project_id:
        project = get_object_or_404(Project, **{'id': project_id})
    elif project_slug:
        project = get_object_or_404(Project, **{'project_slug': project_slug})

    if request.method == 'POST':
        form = UploadAudioForm(request.POST, request.FILES)
        if form.is_valid():
            # TODO: Validate as .mp3
            if project.build_audio:
                #os.remove(project.build_audio.path)
                project.build_audio.delete()
                project.build_audio_name = None
            project.build_audio = request.FILES['build_audio']
            project.build_audio_name = project.build_audio.name
            project.save()
            return HttpResponseRedirect(f'/projects/{project.id}/')
        else:
            logging.error("Invalid form: %s", form.errors)
    return HttpResponseRedirect(f'/projects/{project.id}/')


def new_project(request):
    "New Project page"
    context = {}
    return render(request, 'core/new_project.html', context)


def avatars(request):
    "Global avatars page"
    context = {
        'avatars': UserAvatar.objects.prefetch_related('aliases')\
                                     .order_by('name'),
        'page_view': 'avatars',
    }
    # Pagination
    paginator = Paginator(context['avatars'], 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    context['page_obj'] = page_obj
    return render(request, 'core/avatars.html', context)


def project_avatars(request, project_id=None, project_slug=None):
    "Project avatars page"
    if project_id:
        project = get_object_or_404(Project, **{'id': project_id})
    elif project_slug:
        project = get_object_or_404(Project, **{'project_slug': project_slug})

    try:
        project_data = project.analyze_log()
    except Exception as e:
        logging.error("Error analyzing project log: {0}".format(str(e)))
        project_data = {}
    contributors_list = project_data.get('users', [])
    context = {
        'project': project,
        'contributors': contributors_list,
        'avatars': ProjectUserAvatar.objects.prefetch_related('aliases')\
                                                  .filter(project_id=project.id)\
                                                  .order_by('name'),
        'page_view': 'project_avatars',
    }
    # Pagination
    paginator = Paginator(context['avatars'], 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    context['page_obj'] = page_obj
    return render(request, 'core/avatars.html', context)


def build_queue(request):
    "Build Queue page"
    context = {
        'builds': ProjectBuild.objects.select_related('project')\
                                     .order_by('-id'),
    }
    # Pagination
    paginator = Paginator(context['builds'], 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    context['page_obj'] = page_obj
    return render(request, 'core/build_queue.html', context)


def about(request):
    "About page"
    context = {}
    return render(request, 'core/about.html', context)


#####################


def fetch_log(request):
    response = ''
    user_url = request.GET.get('url', None)
    if user_url is None:
        sample_url = "https://github.com/acaudwell/Gource"
        response = "Use <code>?url=...</code> to request log."
        response += "<br /><br />"
        response += f"Sample: <a href=\"/?url={sample_url}\">{sample_url}</a>"
        return HttpResponse(response)

    try:
        start_time = time.monotonic()
        content = test_http_url(user_url)
        test_time = time.monotonic() - start_time

        start_time = time.monotonic()
        log_data, log_hash, log_subject = download_git_log(user_url, branch="master")
        log_time = time.monotonic() - start_time
        total_time = time.monotonic() - start_time
        post_time = time.monotonic()

        log_info = analyze_gource_log(log_data)
        response = f"<b>URL:</b> <a href=\"{user_url}\" target=\"_blank\">{user_url}</a><br />"
        response += f"<b>Date Range:</b> {log_info['start_date']} -- {log_info['end_date']}<br />"
        response += f"<b>Latest Commit:</b> {log_subject} ({log_hash})<br />"
        response += f"<b># Commits:</b> {log_info['num_commits']} ({log_info['num_commit_days']} commit days)<br />"
        response += f"<b>Committers:</b> {', '.join(log_info['users'])}<br /><br />"
        analyze_time = time.monotonic() - post_time
        response += f"<b>Time Taken:</b> {total_time:.3f} sec (+ {test_time:.3f} test / {analyze_time:.3f} process)<br /><hr />"
        response += f"<pre>{log_data}</pre>"
    except urllib.error.URLError as e:
        response = f'URL/HTTP error: {e.reason}'
    except Exception as e:
        logging.exception("Uncaught exception")
        response = f'Server error: [{e.__class__.__name__}] {e}'
    return HttpResponse(response)



def queue_video(request):
    response = ''
    user_url = request.GET.get('url', None)
    if user_url is None:
        response = "Use <code>?url=...</code> to request video."
        return HttpResponse(response, status=400)

    try:
        project = Project.objects.get(project_url=user_url)
        if request.GET.get('branch', None):
            if project.project_branch != request.GET['branch']:
                project.project_branch = request.GET['branch']
                project.save(update_fields=['project_branch'])
    except Project.DoesNotExist:
        project = Project(
            name=os.path.basename(user_url).rstrip('/'),
            project_url=user_url,
        )
        if request.GET.get('branch', None):
            project.project_branch = request.GET['branch']
        project.save()

    # Check if project currently has queued build
    if project.builds.filter(status__in=['pending', 'queued', 'running']).count():
        response = "ERROR: Project already has pending builds.<br /><br />"
        response += f'<a href="/projects/{project.id}/">{project.project_url}</a>'
        return HttpResponse(response, status=400)

    try:
        # Download latest VCS branch; generate Gource log
        start_time = time.monotonic()
        content = test_http_url(user_url)
        log_data, log_hash, log_subject = download_git_log(user_url, branch=project.project_branch)
        project.project_log_commit_hash = log_hash
        project.project_log_commit_preview = log_subject
        # Get time/author from last entry
        latest_commit = log_data.splitlines()[-1].split('|')
        project.project_log_commit_time = make_aware(datetime.utcfromtimestamp(int(latest_commit[0])))
        if project.project_log:
            #os.remove(project.project_log.path)
            project.project_log.delete()
        project.project_log.save('gource.log', ContentFile(log_data))

        # Create new build (immediately in "queued" state)
        build = ProjectBuild(
            project=project,
            project_branch=project.project_branch,
            status='queued',
            queued_at=utc_now()
        )
        build.save()

        # Send to background worker
        generate_gource_build.delay(build.id)

        response = 'Build has been queued successfully.<br /><br />'
        response += f'Project Page: <a href="/projects/{project.id}/">/projects/{project.id}/</a><br />'
        response += f'Pending Build: <a href="/queue/">/queue/</a> (ID={build.id})<br />'

    except urllib.error.URLError as e:
        response = f'URL/HTTP error: {e.reason}'
    except Exception as e:
        logging.exception("Uncaught exception")
        response = f'Server error: [{e.__class__.__name__}] {e}'
    return HttpResponse(response)


def make_video(request):
    response = ''
    user_url = request.GET.get('url', None)
    if user_url is None:
        response = "Use <code>?url=...</code> to request video."
        return HttpResponse(response, status=400)

    try:
        project = Project.objects.get(project_url=user_url)
    except Project.DoesNotExist:
        project = Project(
            name=os.path.basename(user_url).rstrip('/'),
            project_url=user_url,
        )
        project.save()

    try:
        start_time = time.monotonic()
        content = test_http_url(user_url)
        log_data, log_hash, log_subject = download_git_log(user_url, branch="master")
        project.project_log_commit_hash = log_hash
        project.project_log_commit_preview = log_subject
        # Get time/author from last entry
        latest_commit = log_data.splitlines()[-1].split('|')
        project.project_log_commit_time = make_aware(datetime.utcfromtimestamp(int(latest_commit[0])))
        if project.project_log:
            #os.remove(project.project_log.path)
            project.project_log.delete()
        project.project_log.save('gource.log', ContentFile(log_data))

        # Create new build
        build = ProjectBuild(
            project=project,
            project_branch=project.project_branch,
            status='queued',
            queued_at=utc_now()
        )
        build.save()
        try:
            # Gource log
            build.project_log.save('gource.log', ContentFile(log_data))

            # Generate video
            final_path = generate_gource_video(log_data, seconds_per_day=0.01)
            response = 'Video created successfully.<br /><br />'
            process_time = time.monotonic() - start_time

            build.duration = int(get_video_duration(final_path))
            build.size = os.path.getsize(final_path)

            # Save video content
            with open(final_path, 'rb') as f:
                build.content.save('video.mp4', File(f))
            try:
                screen_data = get_video_thumbnail(final_path, secs=-1, width=1280)
                build.screenshot.save('screenshot.jpg', screen_data)
            except:
                logging.exception("Failed to generate screenshot")

            # Generate thumbnail
            try:
                thumb_data = get_video_thumbnail(final_path, secs=-1)
                build.thumbnail.save('thumb.jpg', thumb_data)
            except:
                logging.exception("Failed to generate thumbnail")
            build.mark_completed()
        except Exception as e:
            build.mark_errored(str(e))
            raise

        response += f'File saved: {project.id} -- {project.project_log.path}<br />'
        response += f"<b>File:</b> {final_path}<br />"
        response += f"<b>Size:</b> {os.path.getsize(final_path)} bytes<br />"
        response += f"<b>Time Taken:</b> {process_time:.3f} sec<br />"
    except urllib.error.URLError as e:
        response = f'URL/HTTP error: {e.reason}'
    except Exception as e:
        logging.exception("Uncaught exception")
        response = f'Server error: [{e.__class__.__name__}] {e}'
    return HttpResponse(response)
