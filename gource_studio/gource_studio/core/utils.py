from datetime import datetime
from io import BytesIO
import logging
import math
import os
from pathlib import Path
import re
import shutil
import ssl
import subprocess
import tempfile
import time
import urllib
from urllib.parse import urlparse

from django.conf import settings
from PIL import Image

from .constants import VIDEO_OPTIONS

# Ignore SSL verification
ssl._create_default_https_context = ssl._create_unverified_context

GOURCE_TIMEOUT = 4*60*60    # 4 hours
FFMPEG_TIMEOUT = 4*60*60    # 4 hours


def get_gource():
    return get_executable_path('gource', 'GOURCE_PATH')

def get_git():
    return get_executable_path('git', 'GIT_PATH')
def get_mercurial():
    return get_executable_path('mercurial', 'MERCURIAL_PATH')

def get_ffmpeg():
    return get_executable_path('ffmpeg', 'FFMPEG_PATH')
def get_ffplay():
    return get_executable_path('ffplay', 'FFPLAY_PATH')
def get_ffprobe():
    return get_executable_path('ffprobe', 'FFPROBE_PATH')

def get_executable_path(command, setting_name=None):
    # If set, use custom path configured in settings
    if setting_name:
        if hasattr(settings, setting_name) and getattr(settings, setting_name):
            return getattr(settings, setting_name)
    # Locate path using `which`
    _which = shutil.which(command)
    if _which:
        return _which
    raise RuntimeError(f"Executable path for '{command}' not found")


def test_http_url(url):
    if not re.match(r'https?:\/\/', url):
        raise ValueError("URL must be a valid HTTP resource")

    # Test resource (using HEAD)
    req = urllib.request.Request(url, method='HEAD')
    resp = urllib.request.urlopen(req, timeout=10)
    if resp.status in [200]:
        return True
    raise urllib.error.HTTPError(code=resp.status, reason="Request error")


def validate_project_url(url):
    if not re.match(r'https?:\/\/', url):
        raise ValueError("URL must be a valid HTTP resource")

    # Only allow projects from whitelisted domains (in settings)
    info = urlparse(url)
    if info.netloc not in settings.PROJECT_DOMAINS:
        raise ValueError(f"Unauthorized URL domain: {info.netloc}")


def download_git_log(url, branch="master"):
    """
    Generate Gource log from Git repository URL.

    Returns (log_data, latest_hash, latest_subject)
    """
    if not re.match(r'https?:\/\/', url):
        raise ValueError("URL must be a valid HTTP resource")

    tempdir = tempfile.mkdtemp(prefix="gource_")
    print(f"DOWNLOAD TEMPDIR = {tempdir}")
    try:
        tempdir_path = Path(tempdir)
        destdir = tempdir_path / 'vcs_source'
        ## 1 - Clone repository locally (as minimal as possible)
        cmd = [get_git(), 'clone', '--quiet', '--filter=blob:none', '--no-checkout',
               '--single-branch',
               '--branch', branch,
               url, str(destdir)]
        p1 = subprocess.Popen(cmd, cwd=str(tempdir_path),
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        p1.wait(timeout=60)     # 60 seconds
        if p1.returncode:
            # Error
            _stdout, _stderr = p1.communicate()
            raise RuntimeError(f"[{p1.returncode}] Error: {_stderr}")

        ## 2 - Generate Gource log from repository
        #   `gource --output-custom-log ${LOGFILE} ${TMP_REPO_PATH}`
        destlog = tempdir_path / 'gource.log'
        cmd = [get_gource(),
               '--git-branch', branch,
               '--output-custom-log', str(destlog),
               str(destdir)
        ]
        p2 = subprocess.Popen(cmd, cwd=str(tempdir_path),
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        p2.wait(timeout=10)     # 10 seconds
        if p2.returncode:
            # Error
            _stdout, _stderr = p2.communicate()
            raise RuntimeError(f"[{p2.returncode}] Error: {_stderr}")

        ## 3 - Retrieve latest commit hash/subject from repo
        #   `git log` => <HASH>:<SUBJECT>
        commit_hash = None
        commit_subject = None
        cmd = [get_git(), 'log',
               '--pretty=format:%H:%s',
               '-n', '1'
        ]
        destdir_git = destdir / '.git'
        p3 = subprocess.Popen(cmd, cwd=str(tempdir_path), env={'GIT_DIR': str(destdir_git)},
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        p3.wait(timeout=5)      # 5 seconds
        _stdout, _stderr = p3.communicate()
        if p3.returncode:
            # Error (log, but make non-fatal)
            logging.error("Failed to retrieve Git Hash/Subject")
            logging.error(str(_stderr))
        else:
            commit_hash, commit_subject = _stdout.decode('utf-8').split(':', 1)

        # Return result
        with destlog.open() as f:
            data = f.read()
        return data, commit_hash, commit_subject

    finally:
        shutil.rmtree(tempdir)

    raise RuntimeError("Unexpected end")


def download_git_tags(url, branch="master"):
    """
    Retrieve list of tags from  Git repository URL.

    Returns [(timestamp, name)]
    """
    if not re.match(r'https?:\/\/', url):
        raise ValueError("URL must be a valid HTTP resource")

    tempdir = tempfile.mkdtemp(prefix="gource_")
    print(f"DOWNLOAD TEMPDIR = {tempdir}")
    try:
        tempdir_path = Path(tempdir)
        destdir = tempdir_path / 'vcs_source'
        ## 1 - Clone repository locally (as minimal as possible)
        cmd = [get_git(), 'clone', '--quiet', '--filter=blob:none', '--no-checkout',
               '--single-branch',
               '--branch', branch,
               url, str(destdir)]
        p1 = subprocess.Popen(cmd, cwd=str(tempdir_path),
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        p1.wait(timeout=60)     # 60 seconds
        if p1.returncode:
            # Error
            _stdout, _stderr = p1.communicate()
            raise RuntimeError(f"[{p1.returncode}] Error: {_stderr}")


        #git tag --list --format='%(creatordate:iso8601)|%(refname:short)'
        cmd = [get_git(), 'tag',
               '--list',
               '--format=%(creatordate:iso8601)|%(refname:short)']
        p2 = subprocess.Popen(cmd, cwd=str(destdir),
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        p2.wait(timeout=60)
        if p2.returncode:
            # Error
            _stdout, _stderr = p2.communicate()
            raise RuntimeError(f"[{p2.returncode}] Error: {_stderr}")

        tags_output = p2.communicate()[0].decode('utf-8')
        tags_list = []
        for line in tags_output.strip().split('\n'):
            timestamp, _, tag_name = line.partition('|')
            tags_list.append(
                (timestamp, tag_name)
            )
        return tags_list

    finally:
        shutil.rmtree(tempdir)

    raise RuntimeError("Unexpected end")



def generate_gource_video(log_data, video_size='1280x720', framerate=60, avatars=None, default_avatar=None, gource_options=None):
    # Input validation
    if video_size not in VIDEO_OPTIONS:
        raise ValueError(f'Invalid video size: {video_size}')

    gource_options = gource_options if gource_options else {}
    if not isinstance(gource_options, dict):
        raise ValueError(f"Argument 'gource_options' must be a dict: {gource_options}")

    seconds_per_day = gource_options.pop('seconds-per-day', 0.5)
    auto_skip_seconds = gource_options.pop('auto-skip-seconds', 3)

    tempdir = tempfile.mkdtemp(prefix="gource_")
    print(f"VIDEO TEMPDIR = {tempdir}")
    try:
        tempdir_path = Path(tempdir)
        log_path = tempdir_path / 'gource.log'
        # Write log file to disk
        with log_path.open('a') as f:
            f.write(log_data)
        # Use FIFO (named pipe) to pipe Gource PPM output to FFmpeg
        # and run both processes simultaneously
        fifo_path = tempdir_path / 'gource.fifo'
        os.mkfifo(str(fifo_path), 0o666)

        ## 1 - Generate PPM video file from Gource
        cmd = [get_gource(),
                '--stop-at-end',
                '--key',
                '--hide', 'filenames,progress',
                '--highlight-users',
                '--user-scale', '3',
                '--dir-name-depth', '4',
                '--seconds-per-day', str(seconds_per_day),
                '--auto-skip-seconds', str(auto_skip_seconds),
                '--bloom-multiplier', '0.5',
                '--disable-input',
                '--no-vsync',
        ]

        # - Add avatar settings (if provided)
        if avatars:
            cmd += ['--user-image-dir', avatars]
        if default_avatar:
            cmd += ['--default-user-image', default_avatar]

        # - Add resolution options
        cmd += [f'-{video_size}',
                '--output-framerate', str(framerate),
                '--output-ppm-stream', str(fifo_path),
                str(log_path),  # NOTE: must be last argument
        ]
        print(f" ~ Starting Gource")
        p1 = subprocess.Popen(cmd, cwd=str(tempdir_path),
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        logging.info("[STEP 1] %s", p1.args)
        #p1.wait(timeout=GOURCE_TIMEOUT)
        time.sleep(1)   # Wait a short time for Gource to get started
        p1.poll()
        if p1.returncode is not None:
            # Error
            print(" ~ Gource command error - exiting...")
            _stdout, _stderr = p1.communicate()
            raise RuntimeError(f"[{p1.returncode}] Error: {_stderr}")

        ## 2 - Generate video using ffmpeg
        print(f" ~ Starting ffmpeg encoding")
        dest_video = tempdir_path / 'output.mp4'
        cmd = [get_ffmpeg(),
               '-y',
               '-r', str(framerate),
               '-f', 'image2pipe',
               '-vcodec', 'ppm',
               '-i', str(fifo_path),
               '-vcodec', 'libx264',
               '-pix_fmt', 'yuv420p',       # * Change to chroma subsampling 4:2:0 YUV
               '-crf', '23',
               str(dest_video)
        ]
        # * - The chroma subsampling default for FFmpeg (Planar 4:4:4 YUV) will not play in
        #     some browsers that do support H.264, notably Firefox.
        #     Changing to an alternate 4:2:0 value found in H.26x standards seems to work better,
        #     even though it is technically lower quality.

        # Direct FFmpeg stdout/stderr to file to avoid halting due to filled I/O buffer
        # - On long running videos, can cause process to halt waiting for output to be read
        with open(str(tempdir_path / 'ffmpeg.stdout'), 'w') as ffout:
            with open(str(tempdir_path / 'ffmpeg.stderr'), 'w') as fferr:
                p2 = subprocess.Popen(cmd, cwd=str(tempdir_path),
                                      stdout=ffout, stderr=fferr)
                                      #stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                logging.info("[STEP 2] %s", p2.args)
                p2.wait(timeout=FFMPEG_TIMEOUT)
                if p2.returncode:
                    # Error
                    print(" ~ FFmpeg command error - exiting...")
                    #_stdout, _stderr = p2.communicate()
                    #raise RuntimeError(f"[{p2.returncode}] Error: {_stderr}")
                    raise RuntimeError(f"[{p2.returncode}] Error during FFmpeg conversion")

        final_path = f'/tmp/{int(time.time())}.mp4'
        shutil.move(str(dest_video), final_path)
        print(f"+ Final video: {final_path}")
        return final_path

    finally:
        shutil.rmtree(tempdir)

    raise RuntimeError("Unexpected end")


def add_background_audio(video_path, audio_path, loop=True):
    """
    Remux video with provided audio mp3.

    If `loop=True`, will loop audio if shorter than video.
    """
    if not os.path.isfile(video_path):
        raise ValueError(f"File not found: {video_path}")
    if not os.path.isfile(audio_path):
        raise ValueError(f"File not found: {audio_path}")
    elif not audio_path.endswith('.mp3'):
        raise ValueError(f"Audio file must be MP3 format: {audio_path}")

    tempdir = tempfile.mkdtemp(prefix="gource_")
    save_file = None
    try:
        cmd1_out = Path(tempdir) / 'output_1a.mp4'

        # Loop audio with video until shortest ends
        #ffmpeg  -i input.mp4 -stream_loop -1 -i input.mp3 -shortest -map 0:v:0 -map 1:a:0 -y out.mp4
        cmd1 = [get_ffmpeg(),
                '-i', video_path,
                '-stream_loop', '-1',
                '-i', audio_path,
                '-shortest',
                '-map', '0:v:0',
                '-map', '1:a:0',
                '-y',
                cmd1_out
        ]
        p1 = subprocess.Popen(cmd1, cwd=str(tempdir),
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        p1.wait(timeout=FFMPEG_TIMEOUT)
        if p1.returncode:
            # Error
            _stdout, _stderr = p1.communicate()
            raise RuntimeError(f"[{p1.returncode}] Error: {_stderr}")

        # Checkpoint
        save_file = cmd1_out

        # Audio Fadeout (crossfade with silence -> 2.0 sec)
        #ffmpeg -i input.mp4 -filter_complex "aevalsrc=0:d=0.6 [a_silence]; [0:a:0] [a_silence] acrossfade=d=0.6" output.mp4
        cmd2_out = Path(tempdir) / 'output_1b.mp4'
        cmd2 = [get_ffmpeg(),
                '-i', cmd1_out,
                '-filter_complex',
                'aevalsrc=0:d=2.0 [a_silence]; [0:a:0] [a_silence] acrossfade=d=2.0',
                cmd2_out
        ]
        p2 = subprocess.Popen(cmd2, cwd=str(tempdir),
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        p2.wait(timeout=FFMPEG_TIMEOUT)
        if p2.returncode:
            # Error
            _stdout, _stderr = p2.communicate()
            raise RuntimeError(f"[{p2.returncode}] Error: {_stderr}")

        save_file = cmd2_out

    finally:
        if save_file:
            final_path = f'/tmp/{int(time.time())}.mp4'
            shutil.move(save_file, final_path)
            video_path = final_path
        shutil.rmtree(tempdir)

    return video_path


def remove_background_audio(video_path):
    """
    Remux video with audio track removed.
    """
    if not os.path.isfile(video_path):
        raise ValueError(f"File not found: {video_path}")

    tempdir = tempfile.mkdtemp(prefix="gource_")
    save_file = None
    try:
        cmd1_out = Path(tempdir) / 'output_nosound.mp4'

        # Use `-vcodec copy` to avoid reencoding video
        #     `-an` disables audio stream selection
        #ffmpeg -i input.mp4 -vcodec copy -an output.mp4
        cmd1 = [get_ffmpeg(),
                '-i', video_path,
                '-vcodec', 'copy',
                '-an',
                cmd1_out
        ]
        p1 = subprocess.Popen(cmd1, cwd=str(tempdir),
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        p1.wait(timeout=FFMPEG_TIMEOUT)
        if p1.returncode:
            # Error
            _stdout, _stderr = p1.communicate()
            raise RuntimeError(f"[{p1.returncode}] Error: {_stderr}")

        save_file = cmd1_out

    finally:
        if save_file:
            final_path = f'/tmp/{int(time.time())}.mp4'
            shutil.move(save_file, final_path)
            video_path = final_path
        shutil.rmtree(tempdir)

    return video_path


def get_video_duration(video_path):
    "Query duration of video file"
    if not os.path.isfile(video_path):
        raise ValueError(f"File not found: {video_path}")
    cmd = [get_ffprobe(),
           '-loglevel', 'error',
           '-of', 'csv=p=0',
           '-show_entries',
           'format=duration',
           video_path
    ]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    p.wait()
    _stdout, _stderr = p.communicate()
    if p.returncode:
        # Error
        raise RuntimeError(f"[{p.returncode}] Error: {_stderr}")
    return float(_stdout)


def rescale_image(image_path, width=256):
    """
    Rescale an image to the specified width (preserving aspect ratio)

    Returns BytesIO object containing image (JPEG)
    """
    # https://stackoverflow.com/a/451580
    img = Image.open(image_path)
    wpercent = (width / float(img.size[0]))
    hsize = int((float(img.size[1]) * float(wpercent)))
    img = img.resize((width, hsize), Image.ANTIALIAS)
    bf = BytesIO()
    img.save(bf, "JPEG")
    return bf


def get_video_thumbnail(video_path, width=512, secs=None, percent=None):
    "Get a thumbnail from file using seconds or duration percentage"
    video_duration = get_video_duration(video_path)
    if secs is not None:
        if abs(secs) > video_duration:
            raise ValueError(f"Value 'secs' exceeds video duration: {video_duration} secs")
        if secs < 0:    # Subtract from end
            secs = video_duration + secs
    elif percent is not None:
        if percent < 0 or percent > 100:
            raise ValueError(f"Value 'percent' must be between 0-100")
        if percent == 0:
            secs = video_duration
        elif percent == 100:
            secs = 0
        else:
            secs = video_duration * (percent/100)
    else:
        raise ValueError("Must provide either 'secs' or 'percent'")

    # Must be even number
    secs = math.floor(secs)

    tempdir = tempfile.mkdtemp(prefix="gource_")
    try:
        thumb_output = Path(tempdir) / 'thumb.jpg'
        cmd = [get_ffmpeg(),
               '-i', video_path,
               '-ss', str(secs),
               '-vf', f'scale={width}:-1',
               '-vframes', '1',
               str(thumb_output)
        ]
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        p.wait()
        _stdout, _stderr = p.communicate()
        if p.returncode:
            # Error
            raise RuntimeError(f"[{p.returncode}] Error: {_stderr}")
        with thumb_output.open('rb') as f:
            return BytesIO(f.read())
    finally:
        shutil.rmtree(tempdir)


def analyze_gource_log(data):
    """
    Return some statistics on a provided Gource log

    Format:
        {
            "start_date":       <datetime>,
            "end_date":         <datetime>,
            "num_changes":      <int>
            "num_commits":      <int>
            "num_commit_days":  <int>
            "users":            [<str>, ...]
        }
    """
    lines = data.strip().split('\n')
    start_date = datetime.utcfromtimestamp(int(lines[0].split('|')[0]))
    end_date = datetime.utcfromtimestamp(int(lines[-1].split('|')[0]))
    users = set()
    commit_days = set()
    num_commits = 0
    current_date = None
    for line in lines:
        # <TIME>|<AUTHOR>|<MODIFICATION>|<PATH>[|<COLOR>]
        segments = line.split('|')
        # Add user
        users.add(segments[1])
        # Check date
        commit_date = datetime.utcfromtimestamp(int(segments[0]))
        commit_days.add(commit_date.date())
        if current_date is None or current_date != commit_date:
            num_commits += 1
            current_date = commit_date

    return {
        'start_date': start_date,
        'end_date': end_date,
        'num_changes': len(lines),
        'num_commits': num_commits,
        'num_commit_days': len(commit_days),
        'users': sorted(list(users), key=lambda n: n.lower())
    }


def estimate_gource_video_duration(data, gource_options=None):
    """
    Estimate the duration (in seconds) of a Gource video based on log.

    Uses relevant `gource_options` to determine changes in time:

      `seconds-per-day`   (default=1) - Speed of simulation in seconds per day.
      `auto-skip-seconds` (default=3) - Skip to next entry if nothing happens for a number of seconds.

    Time-based options (mutually exclusive):

      `start-date`  YYYY-MM-DD [HH:mm:ss] - Start with the first entry after the supplied date and optional time.
      `stop-date`   YYYY-MM-DD [HH:mm:ss] - Stop after the last entry prior to the supplied date and optional time.
      `start-position` 0.0 - 1.0 - Begin at some position in the log (between 0.0 and 1.0 or 'random').
      `stop-position`  0.0 - 1.0 - Stop (exit) at some position in the log (does not work with STDIN).

    Returns number of seconds of resulting video.
    """
    lines = data.strip().split('\n')
    start_date = datetime.utcfromtimestamp(int(lines[0].split('|')[0]))
    end_date = datetime.utcfromtimestamp(int(lines[-1].split('|')[0]))

    gource_options = gource_options if gource_options else {}
    seconds_per_day = float(gource_options.get('seconds-per-day', 1.0))
    skip_secs = float(gource_options.get('auto-skip-seconds', 3.0))
    # Amount of days before auto-skip kicks in
    skip_day_limit = math.ceil(skip_secs / seconds_per_day)

    duration = 0.0
    duration += seconds_per_day     # First day
    current_date = start_date
    file_count = 0
    mod_time = 0
    dir_changes = set()
    user_changes = set()
    for line in lines:
        # <TIME>|<AUTHOR>|<MODIFICATION>|<PATH>[|<COLOR>]
        segments = line.split('|')
        # Check user
        user_changes.add( segments[1] )
        # Check date
        commit_date = datetime.utcfromtimestamp(int(segments[0]))
        dir_changes.add( os.path.dirname(segments[3]) )
        if commit_date.date() > current_date.date():
            # Include time taken to "touch" each file in tree
            #if (file_count * 0.1) > seconds_per_day:
            #    duration += ((file_count * 0.1) - seconds_per_day)
            #duration += ((file_count * 0.1) - 0)
            #if mod_time > seconds_per_day:
            #    duration += (mod_time - seconds_per_day)
            #duration += max((len(dir_changes) * 0.25)-seconds_per_day, 0)
            #duration += max((len(dir_changes) * 0.25), 0)
            #duration += (len(dir_changes) * 0.01)
            #duration += (len(user_changes) * 0.1)
            #duration += mod_time
            user_changes = set()
            dir_changes = set()
            mod_time = 0
            file_count = 0
            # Determine number of days that have elapsed since last commit change
            day_gap = (commit_date.date() - current_date.date()).days
            # - Check for auto-size threshold
            if day_gap >= skip_day_limit:
                duration += (seconds_per_day * skip_day_limit)+skip_secs
            else:
                duration += (seconds_per_day * day_gap)
            current_date = commit_date
        else:
            file_count += 1

    VIDEO_BUFFER = 5    # 5 second still at end
    #return duration
    return duration + VIDEO_BUFFER
