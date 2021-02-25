import logging
import os
from pathlib import Path
import shutil
import tempfile
import time

from celery import shared_task
from django.core.files import File
from django.core.files.base import ContentFile

from .constants import GOURCE_OPTIONS
from .models import Project, ProjectBuild, UserAvatar, ProjectUserAvatar
from .utils import (
    add_background_audio,   #(video_path, audio_path, loop=True):
    analyze_gource_log,     #(data):
    download_git_log,       #(url, branch="master"):
    generate_gource_video,  #(log_data, seconds_per_day=0.1, framerate=60, avatars=None, default_avatar=None):
    get_video_duration,     #(video_path):
    get_video_thumbnail,    #(video_path, width=512, secs=None, percent=None):
    rescale_image,          #(image_path, width=256)
    test_http_url,          #(url):
)

logger = logging.getLogger(__name__)


@shared_task
def generate_gource_build(build_id):
    try:
        build = ProjectBuild.objects.get(id=build_id)
    except ProjectBuild.DoesNotExist:
        logger.error("Invalid build ID: %s", build_id)
        return

    if build.status != 'queued':
        logger.error("Invalid build status: (ID=%s, status=%s). Expecting \"queued\"...", build.status)
        return

    # Begin processing
    build.mark_running()
    start_time = time.monotonic()

    tempdir = tempfile.mkdtemp(prefix="gource_")
    print(f"CELERY BUILD TEMPDIR = {tempdir}")
    try:
        tempdir_path = Path(tempdir)

        # Read in project Gource log
        with open(build.project.project_log.path, 'r') as f:
            log_data = f.read()

        log_info = analyze_gource_log(log_data)
        contributors = set(log_info['users'])
        avatar_options = {}
        avatar_map = {}
        avatar_dir = None

        # Set up avatars
        try:
            global_avatars = UserAvatar.objects.all().prefetch_related('aliases')
            project_avatars = ProjectUserAvatar.objects.filter(project_id=build.project_id).prefetch_related('aliases')
            for av in list(project_avatars) + list(global_avatars):
                for name in [av.name] + list(av.aliases.all().values_list('name', flat=True)):
                    if name not in avatar_options:
                        avatar_options[name] = av.image.path

            # Look through contributors for avatars
            for name in contributors:
                if name in avatar_options:
                    avatar_map[name] = avatar_options[name]

            # If found, make avatars folder
            if avatar_map:
                avatar_dir = tempdir_path / 'avatars'
                if not os.path.isdir(avatar_dir):
                    os.makedirs(avatar_dir)
                for name, image_path in avatar_map.items():
                    # Add symlink for each discovered name in avatar folder
                    #  e.g. {NAME}.jpg
                    ext = os.path.splitext(image_path)[1]
                    dst_name = f"{name}{ext}"
                    os.symlink(image_path, avatar_dir / dst_name)
        except:
            logger.exception("Failed to generate avatar folder")

        # Generate video
        gource_options = {}
        # - Load build options from table
        for option in build.options.all():
            if option.name in GOURCE_OPTIONS:
                gource_options[option.name] = option.value
        #final_path = generate_gource_video(log_data, avatars=avatar_dir, gource_options={'--seconds-per-day': 0.01})
        final_path = generate_gource_video(log_data, avatars=avatar_dir, gource_options=gource_options)
        process_time = time.monotonic() - start_time
        logger.info("Processing time: %s sec", process_time)
        build.duration = int(get_video_duration(final_path))

        # Add background audio (optional)
        try:
            if build.project.build_audio:
                audio_path = build.project.build_audio.path
                if os.path.isfile(audio_path):
                    logger.info("Beginning audio mixing...")
                    final_path = add_background_audio(final_path, audio_path, loop=True)
        except:
            logger.exception("Failed to mix background audio")

        # Save video content
        build.size = os.path.getsize(final_path)
        logger.info("Saving video (%s bytes)...", build.size)
        with open(final_path, 'rb') as f:
            build.content.save('video.mp4', File(f))

        logger.info("Generating screenshots...")
        try:
            screen_data = get_video_thumbnail(final_path, secs=-1, width=1280)
            build.screenshot.save('screenshot.jpg', screen_data)
        except:
            logger.exception("Failed to generate screenshot")

        # Generate thumbnail (by rescaling screenshot)
        try:
            #thumb_data = get_video_thumbnail(final_path, secs=-1)
            thumb_data = rescale_image(build.screenshot.path, width=256)
            build.thumbnail.save('thumb.jpg', thumb_data)
        except:
            logger.exception("Failed to generate thumbnail")

        # Finishing steps
        build.mark_completed()

    except Exception as e:
        build.mark_errored(error_description=str(e))
        logger.exception("Unhandled task error while generating video")
    finally:
        shutil.rmtree(tempdir)
