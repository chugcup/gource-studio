from datetime import datetime, timedelta
import json
import logging
import os
import ssl
import time
import urllib

from django import forms
from django.conf import settings
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.core.files import File
from django.core.files.base import ContentFile
from django.core.paginator import Paginator
from django.db.models import DateTimeField, Exists, Max, OuterRef, Prefetch, Q, Subquery, Value
from django.db.models.functions import Coalesce, Greatest
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render, redirect
from django.utils import dateparse
from django.utils.timezone import make_aware, now as utc_now
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.static import serve

# Ignore SSL verification
ssl._create_default_https_context = ssl._create_unverified_context

from .constants import GOURCE_OPTIONS, GOURCE_OPTIONS_LIST, GOURCE_OPTIONS_JSON
from .models import Project, ProjectBuild, ProjectBuildOption, ProjectCaption, ProjectOption, ProjectUserAvatar, UserAvatar
from .tasks import generate_gource_build
from .utils import (
    add_background_audio,   #(video_path, audio_path, loop=True):
    analyze_gource_log,     #(data):
    download_git_log,       #(url, branch="master"):
    download_git_tags,      #(url, branch="master"):
    estimate_gource_video_duration,
    generate_gource_video,  #(log_data, video_size='1280x720', framerate=60, gource_options={}):
    get_video_duration,     #(video_path):
    get_video_thumbnail,    #(video_path, width=512, secs=None, percent=None):
    remove_background_audio,#(video_path):
    test_http_url,          #(url):
    validate_project_url,   #(url):
)

SITE_NAME = settings.SITE_NAME


def _get_project_permissions(project, actor):
    # There's gotta be a simpler way...
    perms = {}
    # Determine CRUD actions
    for action in ['view', 'edit', 'delete']:
        perms[action] = project.check_permission(actor, action)
    # Determine 'role'
    if actor.is_superuser or actor == project.created_by:
        perms['role'] = 'maintainer'
    elif not actor.is_anonymous:
        member = project.members.filter(user=actor).first()
        if member:
            perms['role'] = member.role
    return perms


#############################################################################
##  Main Views
#############################################################################


def login(request):
    "User Login"
    if request.user.is_authenticated:
        return redirect('index')

    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            auth_login(request, user)
            # Redirect to a success page.
            return redirect('index')
            #return render(request, 'core/login.html', context)
        else:
            # Return an 'invalid login' error message.
            context = {
                'document_title': f'Login - {SITE_NAME}',
                'nav_page': '',
                'error': 'Invalid username/password',
            }
            return render(request, 'core/login.html', context)

    context = {
        'document_title': f'Login - {SITE_NAME}',
        'nav_page': '',
    }
    return render(request, 'core/login.html', context)


def logout(request):
    "User Logout"
    auth_logout(request)
    # Allow for redirecting back to same page (via Referer)
    referer = request.META.get("HTTP_REFERER")
    if referer:
        # Clean the Referer value by scrubbing everything but 'path' and 'query'
        ref_safe = urllib.parse.urlparse(referer)
        next_path = ref_safe.path
        if ref_safe.query:
            next_path = f"{next_path}?{ref_safe.query}"
        return redirect(next_path)
    # Fallback to home page
    return redirect('index')


def index(request):
    "Landing page"
    # Return latest 8 projects
    # - Subquery filter removes any projects without a successful build
    projects_list = Project.objects.filter_permissions(request.user)\
                                   .with_latest_build()\
                                   .annotate(latest_build_time=Max('builds__completed_at'))\
                                   .filter(
                                       Exists(ProjectBuild.objects.filter(project=OuterRef('pk'))\
                                                                  .exclude(content=''))
                                   )
    context = {
        'document_title': f'{SITE_NAME} - Generate Video Timelines of Software Projects',
        'nav_page': '',
        'projects': projects_list.order_by('-latest_build_time')[:8],
    }
    return render(request, 'core/index.html', context)


def projects(request):
    "Projects page"
    sort_key = request.GET.get('sort_key', None)
    if sort_key not in ['id']:
        sort_key = 'latest_activity_time'   # Default
        #sort_key = 'latest_build_time'  # Default
    queryset = Project.objects.filter_permissions(request.user)\
                      .with_latest_build()\
                      .annotate(
                        latest_build_time=Coalesce(
                            Max('builds__completed_at'),
                            Value('1970-01-01 00:00:00', output_field=DateTimeField())
                        )
                      )\
                      .annotate(
                        latest_activity_time=Greatest('created_at', 'latest_build_time')
                      )
    search = request.GET.get('search', None)
    if search:
        queryset = queryset.filter(Q(name__icontains=search)|Q(project_url__contains=search))
    context = {
        'document_title': f'Projects - {SITE_NAME}',
        'nav_page': 'projects',
        'projects': queryset.order_by(f'-{sort_key}'),
        'search': search,
    }
    # Pagination
    paginator = Paginator(context['projects'], 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    context['page_obj'] = page_obj
    return render(request, 'core/projects.html', context)


@ensure_csrf_cookie
def project_details(request, project_id=None, project_slug=None, build_id=None):
    "Project Details page"
    queryset = Project.objects.filter_permissions(request.user)
    if project_id:
        project = get_object_or_404(queryset, **{'id': project_id})
    elif project_slug:
        project = get_object_or_404(queryset, **{'project_slug': project_slug})

    build = None
    is_latest_build = True
    if build_id is not None:
        # Explicit build being referenced
        build = get_object_or_404(ProjectBuild, **{'project_id': project.id, 'id': build_id})
        # project_options = project.options.all()
        project_options = build.options.all() if build else project.options.all()
        is_latest_build = build.id == project.latest_build.id if project.latest_build else False
    else:
        # Latest build/view
        build = project.latest_build
        project_options = project.options.all()
        is_latest_build = True
    project_captions = project.captions.all().order_by('timestamp')

    # Allow for deleting build
    if build_id and request.method == 'DELETE':
        # Delete build
        build.delete()
        return HttpResponseRedirect(f'/projects/{project.id}/')

    context = {
        'document_title': f'Project - {SITE_NAME}',
        'nav_page': 'projects',
        'body_min_padding': True,
        'project': project,
        'project_permissions': _get_project_permissions(project, request.user),
        'project_options': project_options,
        'project_options_json': [
            json.dumps(opt.to_dict()) for opt in project_options
        ],
        'gource_options': GOURCE_OPTIONS_LIST,
        'gource_options_json': [
            json.dumps(opt) for opt in GOURCE_OPTIONS_JSON
        ],
        'project_captions': project_captions,
        'project_captions_json': [
            json.dumps(cpt.to_dict()) for cpt in project_captions
        ],
        'build': build,
        'is_latest_build': is_latest_build,
        'user_can_edit': project.check_permission(request.user, 'edit')
    }
    return render(request, 'core/project.html', context)


@ensure_csrf_cookie
def edit_project(request, project_id=None, project_slug=None):
    "Edit Project Settings view"
    queryset = Project.objects.filter_permissions(request.user)
    if project_id:
        project = get_object_or_404(queryset, **{'id': project_id})
    elif project_slug:
        project = get_object_or_404(queryset, **{'project_slug': project_slug})
    if request.method not in ['POST', 'PUT', 'PATCH']:
        return HttpResponseRedirect(f'/projects/{project.id}/')

    # Edit video options
    # - Gource build options
    new_options = None
    data = json.loads(request.body)
    logging.error(request.POST)
    logging.error(data)

    # TODO: 'video_size'

    # General project fields
    project_updated = False
    update_fields = []
    for field in ['project_slug', 'is_public']:
        if field in data:
            setattr(project, field, data[field])
            project_updated = True
            update_fields.append(field)

    if 'gource_options' in data:
        if isinstance(data['gource_options'], dict):
            new_options = []
            for option, value in data['gource_options'].items():
                if option in GOURCE_OPTIONS:
                    gource_opt = GOURCE_OPTIONS[option]
                    try:
                        # Parse/validate input
                        typed_value = gource_opt['parser'](value)
                        # Stage new set of options
                        new_options.append(
                            ProjectOption(
                                project=project,
                                name=option,
                                value=str(value),
                                value_type=gource_opt['type'],
                            )
                        )
                    except Exception as e:
                        logging.exception(f"Gource option error: {option} => {value}")
                        response = {"error": True, "message": f"Gource option error: {option} => {value}"}
                        return HttpResponse(json.dumps(response), status=400, content_type="application/json")
                else:
                    logging.warning(f"Unrecognized option: {option}")
            # Delete old options
            project.options.all().delete()
            # Add new set
            ProjectOption.objects.bulk_create(new_options)
        else:
            logging.error(f"Invalid 'gource_options' provided: {data['gource_options']}")

    # Project Captions list
    if 'captions' in data:
        if isinstance(data['captions'], list):
            new_captions = []
            for idx, caption in enumerate(data['captions']):
                if not isinstance(caption, dict):
                    # TODO error or log?
                    continue
                try:
                    timestamp = make_aware(dateparse.parse_datetime(caption['timestamp']))
                    caption_text = caption['text']
                    new_captions.append(
                        ProjectCaption(project=project, timestamp=timestamp, text=caption_text)
                    )
                except Exception as e:
                    logging.exception(f"Gource caption error [{idx}]")
                    response = {"error": True, "message": f"Gource caption error: [{idx}]"}
                    return HttpResponse(json.dumps(response), status=400, content_type="application/json")
            # Delete old options
            # TODO merge/prune
            project.captions.all().delete()
            # Add new set
            ProjectCaption.objects.bulk_create(new_captions)
        else:
            logging.error(f"Invalid 'captions' list provided: {data['captions']}")

    if project_updated:
        project.save(update_fields=update_fields)

    response = {"error": False, "message": "Project saved successfully."}
    return HttpResponse(json.dumps(response), status=201, content_type="application/json")


@ensure_csrf_cookie
def project_actions(request, project_id=None, project_slug=None):
    "Project Actions view"
    queryset = Project.objects.filter_permissions(request.user)
    if project_id:
        project = get_object_or_404(queryset, **{'id': project_id})
    elif project_slug:
        project = get_object_or_404(queryset, **{'project_slug': project_slug})
    if request.method not in ['POST']:
        return HttpResponseRedirect(f'/projects/{project.id}/')

    data = json.loads(request.body)
    logging.error(request.POST)
    logging.error(data)
    if 'action' not in data:
        response = {"error": True, "message": "Missing 'action' field."}
        return HttpResponse(json.dumps(response), status=400, content_type="application/json")
    if data['action'] not in ['remix_audio', 'load_captions_from_tags']:
        response = {"error": True, "message": "Invalid 'action' value."}
        return HttpResponse(json.dumps(response), status=400, content_type="application/json")

    # Process actions
    # + 'remix_audio' - Add/strip audio from existing video file
    if data['action'] == 'remix_audio':
        if not project.latest_build or not project.latest_build.content:
            response = {"error": True, "message": "No existing build video to remix."}
            return HttpResponse(json.dumps(response), status=400, content_type="application/json")

        # Add background audio (optional)
        build = project.latest_build
        video_path = build.content.path
        try:
            if project.build_audio:
                # Add new audio
                audio_path = project.build_audio.path
                if os.path.isfile(audio_path):
                    logging.info("Beginning audio mixing...")
                    video_path = add_background_audio(video_path, audio_path, loop=True)
            else:
                # Remove audio
                video_path = remove_background_audio(video_path)
            # Save video content
            build.size = os.path.getsize(video_path)
            logging.info("Saving video (%s bytes)...", build.size)
            build.content.delete()
            with open(video_path, 'rb') as f:
                build.content.save('video.mp4', File(f))
            response = {"error": False, "message": "Video mixed successfully."}
        except Exception as e:
            logging.exception("Failed to mix background audio")
            response = {"error": True, "message": "Error: {str(e)}"}

    # + 'load_captions_from_tags' - Populate captions from project's tags
    elif data['action'] == 'load_captions_from_tags':
        try:
            content = test_http_url(project.project_url)
            tags_list = download_git_tags(project.project_url, branch=project.project_branch)
            for timestamp, tag_name in tags_list:
                captions_added = 0
                try:
                    caption, created = ProjectCaption.objects.get_or_create(
                        project=project,
                        timestamp=timestamp,
                        text=tag_name
                    )
                    if created:
                        captions_added += 1
                except Exception as e:
                    logging.error("Failed to load caption: %s", str(e))
            response = {"error": False, "message": "Tags loaded successfully."}
        except Exception as e:
            logging.exception("Failed to retrieve project tags")
            response = {"error": True, "message": "Error: {str(e)}"}

    return HttpResponse(json.dumps(response), status=201 if not response['error'] else 400, content_type="application/json")


def project_builds(request, project_id=None, project_slug=None):
    "Project Builds page"
    queryset = Project.objects.filter_permissions(request.user)
    if project_id:
        project = get_object_or_404(queryset, **{'id': project_id})
    elif project_slug:
        project = get_object_or_404(queryset, **{'project_slug': project_slug})
    context = {
        'document_title': f'Project Builds - {SITE_NAME}',
        'nav_page': 'projects',
        'project': project,
        'project_permissions': _get_project_permissions(project, request.user),
        'builds': ProjectBuild.objects.select_related('project')\
                                     .filter(project=project)\
                                     .order_by('-id'),
        'user_can_edit': project.check_permission(request.user, 'edit')
    }
    # Pagination
    paginator = Paginator(context['builds'], 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    context['page_obj'] = page_obj
    return render(request, 'core/project_builds.html', context)


def project_build_screenshot(request, project_id=None, project_slug=None, build_id=None):
    "Project Build screenshot"
    queryset = Project.objects.filter_permissions(request.user)
    if project_id:
        project = get_object_or_404(queryset, **{'id': project_id})
    elif project_slug:
        project = get_object_or_404(queryset, **{'project_slug': project_slug})
    else:
        get_object_or_404(Project, **{'id': None})  # Force 404
    # Get by specific build # (or latest build)
    if build_id is not None:
        build = get_object_or_404(ProjectBuild, **{'project_id': project.id, 'id': build_id})
    else:
        build = project.latest_build
        if build is None:
            get_object_or_404(ProjectBuild, **{'id': None}) # Force 404
    filepath = build.screenshot.path
    return serve(request, os.path.basename(filepath), os.path.dirname(filepath))


def project_build_thumbnail(request, project_id=None, project_slug=None, build_id=None):
    "Project Build thumbnail"
    queryset = Project.objects.filter_permissions(request.user)
    if project_id:
        project = get_object_or_404(queryset, **{'id': project_id})
    elif project_slug:
        project = get_object_or_404(queryset, **{'project_slug': project_slug})
    else:
        get_object_or_404(Project, **{'id': None})  # Force 404
    # Get by specific build # (or latest build)
    if build_id is not None:
        build = get_object_or_404(ProjectBuild, **{'project_id': project.id, 'id': build_id})
    else:
        build = project.latest_build
        if build is None:
            get_object_or_404(ProjectBuild, **{'id': None}) # Force 404
    filepath = build.thumbnail.path
    return serve(request, os.path.basename(filepath), os.path.dirname(filepath))


def project_build_video(request, project_id=None, project_slug=None, build_id=None):
    "Project Build video"
    queryset = Project.objects.filter_permissions(request.user)
    if project_id:
        project = get_object_or_404(queryset, **{'id': project_id})
    elif project_slug:
        project = get_object_or_404(queryset, **{'project_slug': project_slug})
    else:
        get_object_or_404(Project, **{'id': None})  # Force 404
    # Get by specific build # (or latest build)
    if build_id is not None:
        build = get_object_or_404(ProjectBuild, **{'project_id': project.id, 'id': build_id})
    else:
        build = project.latest_build
        if build is None:
            get_object_or_404(ProjectBuild, **{'id': None}) # Force 404
    filepath = build.content.path
    return serve(request, os.path.basename(filepath), os.path.dirname(filepath))


def project_build_gource_log(request, project_id=None, project_slug=None, build_id=None):
    "Project (Build) Gource log"
    queryset = Project.objects.filter_permissions(request.user)
    if project_id:
        project = get_object_or_404(queryset, **{'id': project_id})
    elif project_slug:
        project = get_object_or_404(queryset, **{'project_slug': project_slug})

    if build_id is not None:
        # Get build log
        build = get_object_or_404(ProjectBuild, **{'project_id': project.id, 'id': build_id})
        filepath = build.project_log.path
    else:
        filepath = project.project_log.path
    return serve(request, os.path.basename(filepath), os.path.dirname(filepath))


def avatar_image(request, avatar_id):
    "Global avatar image"
    avatar = get_object_or_404(UserAvatar, **{'id': avatar_id})
    filepath = avatar.image.path
    return serve(request, os.path.basename(filepath), os.path.dirname(filepath))


def project_avatar_image(request, project_id=None, project_slug=None, avatar_id=None):
    "Project avatar image"
    queryset = Project.objects.filter_permissions(request.user)
    if project_id:
        project = get_object_or_404(queryset, **{'id': project_id})
    elif project_slug:
        project = get_object_or_404(queryset, **{'project_slug': project_slug})
    avatar = get_object_or_404(ProjectUserAvatar, **{'project_id': project.id, 'id': avatar_id})
    filepath = avatar.image.path
    return serve(request, os.path.basename(filepath), os.path.dirname(filepath))


class UploadAvatarForm(forms.Form):
    name = forms.CharField(max_length=255)
    image = forms.ImageField()

@ensure_csrf_cookie
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
            #response = {"error": False, "message": "Avatar saved successfully."}
            #return HttpResponse(json.dumps(response), status=201, content_type="application/json")
        else:
            logging.error("Invalid form: %s", form.errors)
    return HttpResponseRedirect('/avatars/')


@ensure_csrf_cookie
def project_avatar_upload(request, project_id=None, project_slug=None):
    "Upload a new project avatar"
    queryset = Project.objects.filter_permissions(request.user)
    if project_id:
        project = get_object_or_404(queryset, **{'id': project_id})
    elif project_slug:
        project = get_object_or_404(queryset, **{'project_slug': project_slug})

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
            #response = {"error": False, "message": "Avatar saved successfully."}
            #return HttpResponse(json.dumps(response), status=201, content_type="application/json")
        else:
            logging.error("Invalid form: %s", form.errors)
    return HttpResponseRedirect(f'/projects/{project.id}/avatars/')


class UploadAudioForm(forms.Form):
    build_audio = forms.FileField()

@ensure_csrf_cookie
def project_audio_upload(request, project_id=None, project_slug=None):
    "Upload a new project audio file (MP3)"
    queryset = Project.objects.filter_permissions(request.user)
    if project_id:
        project = get_object_or_404(queryset, **{'id': project_id})
    elif project_slug:
        project = get_object_or_404(queryset, **{'project_slug': project_slug})

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
            #response = {"error": False, "message": "Project saved successfully."}
            #return HttpResponse(json.dumps(response), status=201, content_type="application/json")
        else:
            logging.error("Invalid form: %s", form.errors)
    return HttpResponseRedirect(f'/projects/{project.id}/')


@ensure_csrf_cookie
def project_queue_build(request, project_id=None, project_slug=None):
    queryset = Project.objects.filter_permissions(request.user)
    if project_id:
        project = get_object_or_404(queryset, **{'id': project_id})
    elif project_slug:
        project = get_object_or_404(queryset, **{'project_slug': project_slug})

    # Determine if project log should be re-downloaded
    refetch_log = request.GET.get('refetch_log', None)

    # Check if project currently has queued build
    if project.builds.filter(status__in=['pending', 'queued', 'running']).count():
        response = "ERROR: Project already has pending builds.<br /><br />"
        response += f'<a href="/projects/{project.id}/">{project.project_url}</a>'
        return HttpResponse(response, status=400)

    try:
        if str(refetch_log) in ['t', 'true', '1']:
            # Download latest VCS branch; generate Gource log
            content = test_http_url(project.project_url)
            log_data, log_hash, log_subject, tags_list = download_git_log(project.project_url, branch=project.project_branch)
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

        # Copy over build options from master project
        build_options = []
        for option in project.options.all():
            build_options.append(
                ProjectBuildOption(
                    build=build,
                    name=option.name,
                    value=option.value,
                    value_type=option.value_type
                )
            )
        if build_options:
            ProjectBuildOption.objects.bulk_create(build_options)

        # Save captions to file prior to build
        captions = project.generate_captions_file()
        if captions is not None:
            captions_data = "\n".join(captions)
            build.project_captions.save('captions.txt', ContentFile(captions_data))

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


@ensure_csrf_cookie
def new_project(request):
    "New Project page"
    if not request.user.is_authenticated:
        return HttpResponse(json.dumps({"error": True, "message": "You must have an account to create a project."}), status=403, content_type="application/json")

    # Save a new project
    if request.method == 'POST':
        data = json.loads(request.body)
        for field in ['project_url', 'project_vcs', 'project_branch']:
            if field not in data:
                response = {"error": True, "message": f"[ERROR] Missing required field: {field}"}
                return HttpResponse(json.dumps(response), status=400, content_type="application/json")

        project_url = data['project_url']
        project_vcs = data['project_vcs']
        project_branch = data['project_branch']
        project_is_public = data.get('is_public', True)
        if project_vcs not in [ch[0] for ch in Project.VCS_CHOICES]:
            response = {"error": True, "message": f"[ERROR] Invalid VCS option: {project_vcs}"}
            return HttpResponse(json.dumps(response), status=400, content_type="application/json")
        if not project_branch:
            response = {"error": True, "message": f"[ERROR] Must provide project branch"}
            return HttpResponse(json.dumps(response), status=400, content_type="application/json")

        # Validate URL string (and domain)
        project_url = project_url.rstrip()
        try:
            validate_project_url(project_url)
        except Exception as e:
            response = {"error": True, "message": f"[ERROR] {str(e)}"}
            return HttpResponse(json.dumps(response), status=400, content_type="application/json")

        # Check that project does not exist (identified by URL)
#        try:
#            Project.objects.get(project_url=project_url)
#            response = {"error": True, "message": f"[ERROR] Project already exists matching that URL"}
#            return HttpResponse(json.dumps(response), status=400, content_type="application/json")
#        except Project.DoesNotExist:
#            pass

        # Test that URL is reachable
        # NOTE: some domains don't support HEAD/OPTIONS requests...
        try:
            test_http_url(project_url)
        except Exception as e:
            response = {"error": True, "message": f"[ERROR][TEST] {str(e)}"}
            return HttpResponse(json.dumps(response), status=400, content_type="application/json")

        # Download initial project data
        try:
            if project_vcs == 'git':
                log_data, log_hash, log_subject, tags_list = download_git_log(project_url, branch=project_branch)
            elif project_vcs == 'hg':
                # TODO
                response = {"error": True, "message": f"[ERROR] Mercurial download not supported"}
                return HttpResponse(json.dumps(response), status=400, content_type="application/json")
            else:
                response = {"error": True, "message": f"[ERROR] Invalid VCS option: {project_vcs}"}
                return HttpResponse(json.dumps(response), status=400, content_type="application/json")
        except Exception as e:
            response = {"error": True, "message": f"[ERROR] {str(e)}"}
            return HttpResponse(json.dumps(response), status=400, content_type="application/json")

        project_name = os.path.basename(project_url.rstrip('/'))
        project = Project(
            name=project_name,
            project_url=project_url,
            project_vcs=project_vcs,
            project_branch=project_branch,
            created_by=request.user
        )
        # Set project private
        if not project_is_public:
            project.is_public = False
        # Populate attributes from source download
        if log_hash:
            project.project_log_commit_hash = log_hash
        if log_subject:
            project.project_log_commit_preview = log_subject
        # Get time/author from last entry
        if log_data:
            latest_commit = log_data.splitlines()[-1].split('|')
            project.project_log_commit_time = make_aware(datetime.utcfromtimestamp(int(latest_commit[0])))
        project.save()

        # Load initial ProjectCaptions from VCS tags
        if 'load_captions_from_tags' in data and data['load_captions_from_tags']:
            try:
                for timestamp, tag_name in tags_list:
                    try:
                        caption, created = ProjectCaption.objects.get_or_create(
                            project=project,
                            timestamp=timestamp,
                            text=tag_name
                        )
                    except Exception as ex:
                        logging.error("Failed to load caption: %s", str(ex))
            except Exception as e:
                logging.error("Failed to retrieve project tags: %s", str(e))

        # Save new Gource log content
        project.project_log.save('gource.log', ContentFile(log_data))
        response = {"error": False, "message": "Project saved successfully.",
                    "data": {"id": project.id}}
        return HttpResponse(json.dumps(response), status=201, content_type="application/json")
    context = {
        'document_title': f'New Project - {SITE_NAME}',
        'nav_page': 'new',
    }
    return render(request, 'core/new_project.html', context)


def avatars(request):
    "Global avatars page"
    context = {
        'document_title': f'Avatars - {SITE_NAME}',
        'nav_page': '',
        'avatars': UserAvatar.objects.prefetch_related('aliases')\
                                     .order_by('name'),
        'page_view': 'avatars',
        'user_can_edit': not request.user.is_anonymous,
    }
    # Pagination
    paginator = Paginator(context['avatars'], 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    context['page_obj'] = page_obj
    return render(request, 'core/avatars.html', context)


def project_avatars(request, project_id=None, project_slug=None):
    "Project avatars page"
    queryset = Project.objects.filter_permissions(request.user)
    if project_id:
        project = get_object_or_404(queryset, **{'id': project_id})
    elif project_slug:
        project = get_object_or_404(queryset, **{'project_slug': project_slug})

    try:
        project_data = project.analyze_log()
    except Exception as e:
        logging.error("Error analyzing project log: {0}".format(str(e)))
        project_data = {}
    contributors_list = project_data.get('users', [])
    context = {
        'document_title': f'Project Avatars - {SITE_NAME}',
        'nav_page': 'projects',
        'project': project,
        'project_permissions': _get_project_permissions(project, request.user),
        'contributors': contributors_list,
        'avatars': ProjectUserAvatar.objects.prefetch_related('aliases')\
                                            .filter(project_id=project.id)\
                                            .order_by('name'),
        'page_view': 'project_avatars',
        'user_can_edit': project.check_permission(request.user, 'edit')
    }
    # Pagination
    paginator = Paginator(context['avatars'], 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    context['page_obj'] = page_obj
    return render(request, 'core/avatars.html', context)


def build_queue(request):
    "Build Queue page"
    queryset = ProjectBuild.objects.select_related('project')
    queryset = queryset.prefetch_related(
        Prefetch('project__builds', to_attr='_cached_latest_build',
                 queryset=ProjectBuild.objects.exclude(content='').order_by('-created_at'))
    )
    # Filter by accessible projects
    projects_list = Project.objects.filter_permissions(request.user)
    queryset = queryset.filter(project__in=projects_list)
    #queryset = queryset.filter(
    search = request.GET.get('search', None)
    if search:
        queryset = queryset.filter(Q(project__name__icontains=search)|Q(project__project_url__contains=search))
    context = {
        'document_title': f'Build Queue - {SITE_NAME}',
        'nav_page': 'queue',
        'builds': queryset.order_by('-id'),
        'search': search,
    }
    # Pagination
    paginator = Paginator(context['builds'], 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    context['page_obj'] = page_obj
    return render(request, 'core/build_queue.html', context)


def about(request):
    "About page"
    context = {
        'document_title': f'About - {SITE_NAME}',
        'nav_page': 'about',
    }
    return render(request, 'core/about.html', context)


#####################


def fetch_log(request):
    response = ''
    user_url = request.GET.get('url', None)
    if user_url is None:
        sample_url = "https://github.com/acaudwell/Gource"
        response = "Use <code>?url=...</code> to request log."
        response += "<br /><br />"
        response += f"Sample: <a href=\"/test/log/?url={sample_url}\">{sample_url}</a>"
        return HttpResponse(response)

    try:
        start_time = time.monotonic()
        content = test_http_url(user_url)
        test_time = time.monotonic() - start_time

        start_time = time.monotonic()
        log_data, log_hash, log_subject, tags_list = download_git_log(user_url, branch="master")
        log_time = time.monotonic() - start_time
        total_time = time.monotonic() - start_time
        post_time = time.monotonic()

        log_info = analyze_gource_log(log_data)
        project_days = (log_info['end_date'] - log_info['start_date']).days
        response = f"<b>URL:</b> <a href=\"{user_url}\" target=\"_blank\">{user_url}</a><br />"
        response += f"<b>Date Range:</b> {log_info['start_date']} -- {log_info['end_date']} ({project_days} days)<br />"
        response += f"<b>Latest Commit:</b> {log_subject} ({log_hash})<br />"
        response += f"<b># Commits:</b> {log_info['num_commits']} ({log_info['num_commit_days']} commit days / {log_info['num_changes']} changes)<br />"
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


def fetch_tags(request):
    response = ''
    user_url = request.GET.get('url', None)
    if user_url is None:
        sample_url = "https://github.com/acaudwell/Gource"
        response = "Use <code>?url=...</code> to request tags."
        response += "<br /><br />"
        response += f"Sample: <a href=\"/test/tags/?url={sample_url}\">{sample_url}</a>"
        return HttpResponse(response)

    try:
        content = test_http_url(user_url)
        tags_list = download_git_tags(user_url, branch="master")
        response = f"<b>URL:</b> <a href=\"{user_url}\" target=\"_blank\">{user_url}</a><br />"
        response += f"<b>Tags List:</b><br />"
        for timestamp, tag_name in tags_list:
            response += f"+ [{timestamp}] <span style=\"padding-left:12px\">{tag_name}</span><br />"
    except urllib.error.URLError as e:
        response = f'URL/HTTP error: {e.reason}'
    except Exception as e:
        logging.exception("Uncaught exception")
        response = f'Server error: [{e.__class__.__name__}] {e}'
    return HttpResponse(response)


def test_queue_video(request):
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
        content = test_http_url(user_url)
        log_data, log_hash, log_subject, tags_list = download_git_log(user_url, branch=project.project_branch)
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
        log_data, log_hash, log_subject, tags_list = download_git_log(user_url, branch="master")
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
            #final_path = generate_gource_video(log_data, gource_options={'--seconds-per-day': 0.01})
            final_path = generate_gource_video(log_data)
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


def estimate_project_duration(request, project_id):
    queryset = Project.objects.filter_permissions(request.user)
    project = get_object_or_404(queryset, **{'pk': project_id})
    latest_build = project.latest_build

    with open(project.project_log.path, 'r') as f:
        data = f.read()

    added = 0
    modded = 0
    deleted = 0
    lines = data.strip().split('\n')
    for line in lines:
        # <TIME>|<AUTHOR>|<MODIFICATION>|<PATH>
        segments = line.split('|')
        if segments[2] == 'A': added += 1
        elif segments[2] == 'M': modded += 1
        elif segments[2] == 'D': deleted += 1

    try:
        spd = float(request.GET.get('seconds-per-day', None))
    except:
        spd = 1.0
    try:
        ass = float(request.GET.get('auto-skip-seconds', None))
    except:
        ass = 3.0

    gource_options = {
        'seconds-per-day': spd,
        'auto-skip-seconds': ass,
    }
    duration = estimate_gource_video_duration(data, gource_options=gource_options)
    td_duration = str(timedelta(seconds=int(duration)))
    response = {
        "duration": duration,
        "duration_str": td_duration
    }
    return HttpResponse(json.dumps(response), content_type='application/json')


def estimate_video_duration(request, project_id):
    "Returns HTML"
    response = ''
    project = get_object_or_404(Project, **{'pk': project_id})
    latest_build = project.latest_build

    with open(project.project_log.path, 'r') as f:
        data = f.read()

    added = 0
    modded = 0
    deleted = 0
    lines = data.strip().split('\n')
    for line in lines:
        # <TIME>|<AUTHOR>|<MODIFICATION>|<PATH>
        segments = line.split('|')
        if segments[2] == 'A': added += 1
        elif segments[2] == 'M': modded += 1
        elif segments[2] == 'D': deleted += 1

    try:
        spd = float(request.GET.get('spd', None))
    except:
        spd = 1.0
    try:
        ass = float(request.GET.get('ass', None))
    except:
        ass = 3.0

    gource_options = {
        'seconds-per-day': spd,
        'auto-skip-seconds': ass,
    }
    duration = estimate_gource_video_duration(data, gource_options=gource_options)
    from datetime import timedelta
    td_duration = str(timedelta(seconds=int(duration)))

    log_info = analyze_gource_log(data)
    project_days = (log_info['end_date'] - log_info['start_date']).days
    response = f"<b>URL:</b> <a href=\"{project.project_url}\" target=\"_blank\">{project.project_url}</a><br />"
    response += f"<b>Date Range:</b> {log_info['start_date']} -- {log_info['end_date']} ({project_days} days)<br />"
    response += f"<b># Commits:</b> {log_info['num_commits']} ({log_info['num_commit_days']} commit days / {log_info['num_changes']} changes)<br />"
    response += f"<b>Added:</b> {added} -- <b>Modified:</b> {modded} -- <b>Deleted:</b> {deleted}<br />"
    response += f"<b>Committers:</b> {', '.join(log_info['users'])}<br /><hr />"

    response += '<table>'
    response += f'<tr><td>Duration:</td><td>{duration} secs</td></tr>'
    response += f'<tr><td>Duration:</td><td>{td_duration}</td></tr>'
    # Get latest build duration
    if latest_build and latest_build.duration:
        td_latest_duration = str(timedelta(seconds=latest_build.duration))
        duration_diff = int(latest_build.duration - duration)
        if duration_diff > 0:
            duration_diff = f'<span style="color:#090">+{duration_diff}</span>'
        else:
            duration_diff = f'<span style="color:#F00">{duration_diff}</span>'
        response += f'<tr><td>Latest Build:</td><td>{td_latest_duration} (<b>{duration_diff}</b>)</td><tr>'
    response += '</table>'

    return HttpResponse(response)
