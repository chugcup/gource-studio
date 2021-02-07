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

from django.conf import settings

# Ignore SSL verification
ssl._create_default_https_context = ssl._create_unverified_context

#GIT = 'git'
#GOURCE = 'gource'

#FFMPEG = '/Users/jeffg/ffmpeg/ffmpeg'
#FFPLAY = '/Users/jeffg/ffmpeg/ffplay'
#FFPROBE = '/Users/jeffg/ffmpeg/ffprobe'

GOURCE_TIMEOUT = 4*60*60    # 4 hours
FFMPEG_TIMEOUT = 10*60      # 10 minutes


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


def generate_gource_video(log_data, seconds_per_day=0.1, framerate=60, avatars=None, default_avatar=None):
    tempdir = tempfile.mkdtemp(prefix="gource_")
    print(f"VIDEO TEMPDIR = {tempdir}")
    try:
        tempdir_path = Path(tempdir)
        log_path = tempdir_path / 'gource.log'
        output_ppm = tempdir_path / 'output.ppm'
        # Write log file to disk
        with log_path.open('a') as f:
            f.write(log_data)
        ## 1 - Generate PPM video file from Gource
        cmd = [get_gource(),
                '--stop-at-end',
                '--key',
                '--hide', 'filenames,progress',
                '--highlight-users',
                '--user-scale', '3',
                '--dir-name-depth', '4',
                '--seconds-per-day', str(seconds_per_day),
                '--auto-skip-seconds', '1',
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
        cmd += ['-1280x720',
                '--output-ppm-stream', str(output_ppm),
                '--output-framerate', str(framerate),
                str(log_path)
        ]
        p1 = subprocess.Popen(cmd, cwd=str(tempdir_path),
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        p1.wait(timeout=GOURCE_TIMEOUT)
        if p1.returncode:
            # Error
            _stdout, _stderr = p1.communicate()
            raise RuntimeError(f"[{p1.returncode}] Error: {_stderr}")

        ## 2 - Generate video using ffmpeg
        dest_video = tempdir_path / 'output.mp4'
        cmd = [get_ffmpeg(),
               '-y',
               '-r', str(framerate),
               '-f', 'image2pipe',
               '-vcodec', 'ppm',
               '-i', str(output_ppm),
               '-vcodec', 'libx264',
               '-crf', '23',
               str(dest_video)
        ]
        p2 = subprocess.Popen(cmd, cwd=str(tempdir_path),
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        p2.wait(timeout=FFMPEG_TIMEOUT)
        if p2.returncode:
            # Error
            _stdout, _stderr = p2.communicate()
            raise RuntimeError(f"[{p2.returncode}] Error: {_stderr}")

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

        ##Loop audio with video until shortest ends
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

        ##Audio Fadeout (crossfade with silence -> 0.6 sec)
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
    for line in lines:
        # <TIME>|<AUTHOR>|<MODIFICATION>|<PATH>
        segments = line.split('|')
        # Add user
        users.add(segments[1])
        # Check date
        commit_date = datetime.utcfromtimestamp(int(segments[0]))
        commit_days.add(commit_date.date())

    return {
        'start_date': start_date,
        'end_date': end_date,
        'num_commits': len(lines),
        'num_commit_days': len(commit_days),
        'users': sorted(list(users), key=lambda n: n.lower())
    }
