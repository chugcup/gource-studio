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
from .exceptions import ProjectBuildAbortedError
from .utils import (
    add_background_audio,   #(video_path, audio_path, loop=True):
    analyze_gource_log,     #(data):
    download_git_log,       #(url, branch="master"):
    format_duration,        #(seconds):
    generate_gource_video,  #(log_data, seconds_per_day=0.1, framerate=60, avatars=None, default_avatar=None):
    get_video_duration,     #(video_path):
    get_video_thumbnail,    #(video_path, width=512, secs=None, percent=None):
    remove_background_audio,#(video_path):
    rescale_image,          #(image_path, width=256)
    resolve_project_avatars,#(project, contributers):
    test_http_url,          #(url):
)

logger = logging.getLogger(__name__)


@shared_task
def generate_gource_build(build_id):
    from .models import Project, ProjectBuild, UserAvatar, ProjectUserAvatar

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

    # If video file already set on build, we are only modifying the audio track (`remix_audio=True`)
    # Depending on the `build_audio` field, we will add or remove audio.
    if build.content:
        tempdir = tempfile.mkdtemp(prefix="gource_")
        try:
            # Add background audio (optional)
            try:
                video_path = build.content.path
                output_path = Path(tempdir) / f"{int(time.time())}.mp4"
                if build.build_audio:
                    build.set_build_stage("audio", "Mixing audio")
                    audio_path = build.build_audio.path
                    logger.info("Beginning audio mixing...")
                    final_path = add_background_audio(video_path, audio_path, loop=True, output_path=output_path)
                else:
                    build.set_build_stage("audio", "Removing audio")
                    final_path = remove_background_audio(video_path, output_path=output_path)
            except:
                logger.exception("Failed to mix background audio")
                raise

            # Save video content
            build.size = os.path.getsize(final_path)
            logger.info("Saving video (%s bytes)...", build.size)
            with open(final_path, 'rb') as f:
                build.content.save('video.mp4', File(f))

            thumbs_start_time = time.monotonic()
            logger.info("Generating thumbnails...")
            build.set_build_stage("thumbnail", "Generating thumbnails")
            try:
                screen_data = get_video_thumbnail(final_path, secs=-1, width=1280)
                build.screenshot.save('screenshot.jpg', screen_data)
            except:
                logger.exception("Failed to generate screenshot")

            # Generate thumbnail (by rescaling screenshot)
            try:
                #thumb_data = get_video_thumbnail(final_path, secs=-1)
                thumb_data = rescale_image(build.screenshot.path, width=256, output_format='JPEG')
                build.thumbnail.save('thumb.jpg', thumb_data)
            except:
                logger.exception("Failed to generate thumbnail")
            logger.info("[+%s] Thumbnails complete", format_duration(time.monotonic() - thumbs_start_time))

            # Finishing steps
            build.mark_completed()
            build.set_build_stage("success", "")
            return
        except Exception as e:
            build.mark_errored(error_description=str(e))
            logger.exception("Unhandled task error while generating video")
        finally:
            shutil.rmtree(tempdir)

    build.set_build_stage("init", "Preparing project assets")
    start_time = time.monotonic()

    tempdir = tempfile.mkdtemp(prefix="gource_")
    print(f"CELERY BUILD TEMPDIR = {tempdir}")
    try:
        tempdir_path = Path(tempdir)

        # Read in project Gource log
        with open(build.project_log.path, 'r') as _file:
            log_data = _file.read()

        log_info = analyze_gource_log(log_data)
        contributors = set(log_info['users'])
        # Set up avatars
        avatar_dir = None
        avatar_map = resolve_project_avatars(build.project, contributors)

        # If found, make avatars folder
        if avatar_map:
            try:
                avatar_dir = tempdir_path / 'avatars'
                if not os.path.isdir(avatar_dir):
                    os.makedirs(avatar_dir)
                for name, avatar_data in avatar_map.items():
                    # Add symlink for each discovered name in avatar folder
                    #  e.g. {NAME}.jpg
                    image_path = avatar_data[0]
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
        captions_path = None
        if build.project_captions:
            captions_path = build.project_captions.path
        logo_file = None
        if build.build_logo:
            logo_file = build.build_logo.path
        background_file = None
        if build.build_background:
            background_file = build.build_background.path

        build.set_build_stage("gource", "Capturing Gource video")
        output_path = Path(tempdir) / f"{int(time.time())}.mp4"
        try:
            final_path = generate_gource_video(
                log_data,
                video_size=build.video_size,
                avatars=avatar_dir,
                captions=captions_path,
                logo_file=logo_file,
                background_file=background_file,
                gource_options=gource_options,
                project_build=build,
                output_path=output_path,
            )
        except ProjectBuildAbortedError:
            logger.info("Project was aborted by user [elapsed: %s]", format_duration(time.monotonic() - start_time))
            return

        logger.info("[+%s] Video capture complete", format_duration(time.monotonic() - start_time))
        build.duration = int(get_video_duration(final_path))

        # Add background audio (optional)
        # TODO support abort
        try:
            if build.build_audio:
                mixer_start_time = time.monotonic()
                build.set_build_stage("audio", "Mixing audio")
                audio_path = build.build_audio.path
                logger.info("Beginning audio mixing...")
                output_path = Path(tempdir) / f"{int(time.time())}_audio.mp4"
                final_path = add_background_audio(final_path, audio_path, loop=True, output_path=output_path)
                logger.info("[+%s] Audio mixing complete", format_duration(time.monotonic() - mixer_start_time))
        except:
            logger.exception("Failed to mix background audio")

        # Save video content
        build.size = os.path.getsize(final_path)
        logger.info("Saving video (%s bytes)...", build.size)
        with open(final_path, 'rb') as f:
            build.content.save('video.mp4', File(f))

        thumbs_start_time = time.monotonic()
        logger.info("Generating thumbnails...")
        build.set_build_stage("thumbnail", "Generating thumbnails")
        try:
            screen_data = get_video_thumbnail(final_path, secs=-1, width=1280)
            build.screenshot.save('screenshot.jpg', screen_data)
        except:
            logger.exception("Failed to generate screenshot")

        # Generate thumbnail (by rescaling screenshot)
        try:
            #thumb_data = get_video_thumbnail(final_path, secs=-1)
            thumb_data = rescale_image(build.screenshot.path, width=256, output_format='JPEG')
            build.thumbnail.save('thumb.jpg', thumb_data)
        except:
            logger.exception("Failed to generate thumbnail")
        logger.info("[+%s] Thumbnails complete", format_duration(time.monotonic() - thumbs_start_time))

        # Finishing steps
        build.mark_completed()
        build.set_build_stage("success", "")

    except Exception as e:
        build.mark_errored(error_description=str(e))
        logger.exception("Unhandled task error while generating video")
    finally:
        shutil.rmtree(tempdir)
