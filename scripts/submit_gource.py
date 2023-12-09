#!/usr/bin/env python3

#############################################################################
# Generate Gource log from current project and upload to server.
#############################################################################
# Version: 1.0.0
#############################################################################


#----------------------------------------------------------
# Update the following to use as defaults
#----------------------------------------------------------
DEFAULT_HOST         = None      # "http://..."
DEFAULT_API_TOKEN    = None      # API access token
DEFAULT_PROJECT_ID   = None      # Project ID -or-
DEFAULT_PROJECT_SLUG = None      #  Project Slug
#----------------------------------------------------------


##### Main Script ###########################################################

import argparse
from datetime import datetime, timezone
import getpass
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request

# API endpoint where log will be uploaded
LOG_TEMPLATE = "{base_url}/api/v1/projects/{project_id}/project_log/"
CAPTIONS_TEMPLATE = "{base_url}/api/v1/projects/{project_id}/captions/"
QUEUE_TEMPLATE = "{base_url}/api/v1/projects/{project_id}/builds/new/"


def main(host, token, project_path, *, project_id=None, project_slug=None, queue_build=False, submit_tags=False):
    if not os.path.isdir(project_path):
        raise RuntimeError(f"Path not valid directory: {project_path}")
    project_type = determine_project_type(project_path)

    # Validate host
    o = urllib.parse.urlparse(host)
    server_host = f"{o.scheme}://{o.netloc}"

    # Determine latest commit details (SHA1 hash, commit subject)
    author_timestamp = None     # UNIX timestamp
    author_timestamp_str = None # Human-readable time
    commit_hash = None
    commit_subject = None
    if project_type == 'git':
        author_timestamp, commit_hash, commit_subject = get_latest_git_commit(project_path)
    elif project_type == 'mercurial':
        author_timestamp, commit_hash, commit_subject = get_latest_mercurial_commit(project_path)
    if author_timestamp:
        author_timestamp_str = datetime.fromtimestamp(author_timestamp, tz=timezone.utc).strftime('%c %z')
    print("#"*78)
    print(f' Last Timestamp: {author_timestamp_str}')
    print(f'    Commit Hash: {commit_hash}')
    print(f' Commit Subject: {commit_subject}')
    print("#"*78)

    gource_path = get_gource_path()
    # Generate log in temp directory
    output_log = tempfile.mkstemp(suffix=".log", prefix="gource_")[1]
    #print(f' - Temporary log path: {output_log}')
    try:
        print("+ Generating Gource log...", end='')
        sys.stdout.flush()
        generate_log(project_path, output_log)
        print(" DONE")
        sys.stdout.flush()

        # Submit log to server
        put_data = {
            'project_log_commit_hash': commit_hash,
            'project_log_commit_time': author_timestamp,
            'project_log_commit_preview': commit_subject
        }
        with open(output_log, 'r') as f:
            put_data['project_log'] = f.read()
        log_url = LOG_TEMPLATE.format(**{
            "base_url": server_host,
            "project_id": project_id if project_id else project_slug
        })

        print("++ Sending update to server...", end='')
        sys.stdout.flush()
        # Submit using Token authentication
        req = urllib.request.Request(log_url, method="PUT", data=json.dumps(put_data).encode('utf-8'), headers={
            'Content-Type': 'application/json',
            'Authorization': f'Token {token}'
        })
        res = urllib.request.urlopen(req)
        if res.status not in [200, 201]:
            print("ERROR")
            print(f"  !! Unexpected HTTP response: {res.status} {res.reason}", file=sys.stderr)
            return
        print(" DONE")
        #shutil.copyfile(output_log, f'./{os.path.basename(output_log)}')

        if submit_tags:
            # Fetch tags from repo and upload as captions
            try:
                tags_list = retrieve_tags_from_git_repo(project_path)
                if tags_list:
                    print(f"++ Sending {len(tags_list)} project tag(s) as captions...", end='')
                    sys.stdout.flush()
                    captions_url = CAPTIONS_TEMPLATE.format(**{
                        "base_url": server_host,
                        "project_id": project_id if project_id else project_slug
                    })
                    captions_data = {
                        "captions": tags_list
                    }
                    # Submit using Token authentication
                    req = urllib.request.Request(captions_url, method="POST", data=json.dumps(captions_data).encode('utf-8'), headers={
                        'Content-Type': 'application/json',
                        'Authorization': f'Token {token}'
                    })
                    res = urllib.request.urlopen(req)
                    if res.status not in [200, 201]:
                        print("ERROR")
                        print(f"  !! Unexpected HTTP response: {res.status} {res.reason}", file=sys.stderr)
                    else:
                        print(" DONE")
                else:
                    print("NOTICE: No tags found in project repository.")
            except Exception as e:
                print("ERROR")
                print(f"  !! Error submitting project tags: {str(e)}")

        if queue_build:
            try:
                print(f"++ Requesting new video build...", end='')
                build_url = QUEUE_TEMPLATE.format(**{
                    "base_url": server_host,
                    "project_id": project_id if project_id else project_slug
                })
                build_data = {}
                # Submit using Token authentication
                req = urllib.request.Request(build_url, method="POST", data=json.dumps(build_data).encode('utf-8'), headers={
                    'Content-Type': 'application/json',
                    'Authorization': f'Token {token}'
                })
                res = urllib.request.urlopen(req)
                if res.status not in [201]:
                    # TODO: Check for existing build queued (400)
                    print("ERROR")
                    print(f"  !! Unexpected HTTP response: {res.status} {res.reason}", file=sys.stderr)
                else:
                    print(" DONE")
            except Exception as e:
                print("ERROR")
                print(f"  !! Error requesting new project build: {str(e)}")

    finally:
        # Cleanup
        if os.path.isfile(output_log):
            os.unlink(output_log)


def generate_log(project_path, output_path):
    #gource --output-custom-log <LOGFILE> [PROJECT_DIR]
    p1 = subprocess.Popen([get_gource_path(), '--output-custom-log', output_path, project_path],
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    p1.wait()
    if p1.returncode:
        raise RuntimeError("Gource log generation failed")


def get_latest_git_commit(project_path):
    #   `git log` => <DATE>:<HASH>:<SUBJECT>
    author_timestamp = None
    commit_hash = None
    commit_subject = None
    cmd = [get_git_path(), 'log',
           '--pretty=format:%at:%H:%s',
           '--max-count', '1'
    ]
    destdir_git = os.path.join(project_path, '.git')
    p1 = subprocess.Popen(cmd, cwd=str(project_path), env={'GIT_DIR': str(destdir_git)},
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    p1.wait(timeout=5)      # 5 seconds
    _stdout, _stderr = p1.communicate()
    if p1.returncode:
        # Error (log, but make non-fatal)
        print("Failed to retrieve Git Hash/Subject", file=sys.stderr)
        print(str(_stderr), file=sys.stderr)
    else:
        author_timestamp, commit_hash, commit_subject = _stdout.decode('utf-8').split(':', 2)
        author_timestamp = int(author_timestamp)
    return author_timestamp, commit_hash, commit_subject


def get_latest_mercurial_commit(project_path):
    #   `hg log` => <DATE>:<HASH>:<SUBJECT>
    author_timestamp = 0
    commit_hash = None
    commit_subject = None
    cmd = [get_mercurial_path(), 'log',
            '--template', '{date|hgdate}:{node}:{desc}',
           '--limit', '1'
    ]
    destdir_hg = os.path.join(project_path, '.hg')
    p1 = subprocess.Popen(cmd, cwd=str(project_path),
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    p1.wait(timeout=5)      # 5 seconds
    _stdout, _stderr = p1.communicate()
    if p1.returncode:
        # Error (log, but make non-fatal)
        print("Failed to retrieve Mercurial Hash/Subject", file=sys.stderr)
        print(str(_stderr), file=sys.stderr)
    else:
        author_timestamp, commit_hash, commit_subject = _stdout.decode('utf-8').split(':', 2)
        # NOTE: returns "<UNIX_TIMESTAMP> <TIMEZONE_OFFSET>"
        author_timestamp = int(author_timestamp.split(" ")[0])
    return author_timestamp, commit_hash, commit_subject


def retrieve_tags_from_git_repo(repo_path):
    """
    Retrieve list of tags from a local Git repository folder.

    Returns [(timestamp, name)]
    """
    if not os.path.isdir(repo_path):
        raise ValueError(f"Invalid Git repo path: {repo_path}")

    #git tag --list --format='%(creatordate:iso8601)|%(refname:short)'
    cmd = [get_git_path(), 'tag',
           '--list',
           '--format=%(creatordate:iso8601)|%(refname:short)']
    p1 = subprocess.Popen(cmd, cwd=repo_path,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    p1.wait(timeout=60)
    if p1.returncode:
        # Error
        _stdout, _stderr = [x.decode('utf-8') for x in p1.communicate()]
        raise RuntimeError(f"[{p1.returncode}] Error: {_stderr}")

    tags_output = p1.communicate()[0].decode('utf-8')
    tags_list = []
    ISO_PATTERN = '%Y-%m-%d %H:%M:%S %z'
    for line in tags_output.strip().split('\n'):
        if not line:
            continue
        timestamp, _, tag_name = line.partition('|')
        tags_list.append({
            "timestamp": datetime.strptime(timestamp, ISO_PATTERN).astimezone(timezone.utc).isoformat(),
            "text": tag_name
        })
    return tags_list


def determine_project_type(path):
    if os.path.isdir(os.path.join(path, '.git')):
        return 'git'
    if os.path.isdir(os.path.join(path, '.hg')):
        return 'mercurial'
    raise RuntimeError(f"Could not determine project type: {path}")

def get_git_path():
    return _which_path('git')

def get_mercurial_path():
    return _which_path('hg')

def get_gource_path():
    return _which_path('gource')

def _which_path(command):
    path = shutil.which(command)
    if path:
        return path
    raise RuntimeError(f"Command '{command}' not found in path.")

def parse_env_file(path):
    "Read in a POSIX environment variable file and load to `os.environ`"
    with open(args.env_file, 'r') as f:
        for line in f.readlines():
            line = line.replace('\n', '')
            if not line or line.startswith('#'):
                continue
            try:
                name, value = line.strip().split('=', 1)
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1] # Strip quotes
                os.environ[name] = value
            except ValueError:
                #print(f"Invalid line: {line}")
                pass

def get_from_env(name, required=True, default=None, message=None):
    "Fetch an environment variable by name"
    value = os.environ.get(name, None)
    if value is None and default is not None:
        value = default
    if value is None and required:
        if not message:
            message = f"Missing required option: {name}"
        raise RuntimeError(message)
    return value


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="""Generate Gource log and submit to Gource Studio server.

This script can be used to update a Gource Studio project log using a local repository,
which may be necessary if the project is not publicly accessible.

In order to upload the project log, you must provide a URL to the Gource Studio server,
an API token for a valid account, and the Project ID or slug to be updated.
These can be provided as command-line arguments, environment variables, or using a
configuration file.

    # Full URL to Gource Studio site    (--host)
    GOURCE_HOST="https://example.com/"

    # Access token for REST API         (--token)
    GOURCE_API_TOKEN="8183b9a6d3a8567c307b5f6ac40239bc6de87f62"

    # Destination project (ID or slug)  (--project-id/--project-slug)
    GOURCE_PROJECT_ID=812
    GOURCE_PROJECT_SLUG="gource-studio"

These can be stored in a POSIX-compliant environment file and provided using
the --env-file argument.

    python3 submit_gource.py --env-file .env --project-id 812

Run from the root directory of your project, or specify a path from the command line.
This will detect the VCS used and generate a Gource log file to upload.
""", formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("path", metavar="PROJECT_DIR", nargs='?', help="Root directory path (default=cwd)")
    parser.add_argument("--host", metavar="HOST", type=str, required=False, help="Full URL to Gource Studio server")
    parser.add_argument("--token", metavar="TOKEN", type=str, required=False, help="API Token used to authenticate upload")
    group1 = parser.add_mutually_exclusive_group()
    group1.add_argument("--project-id", metavar="ID", type=int, required=False, help="Project ID to update")
    group1.add_argument("--project-slug", metavar="NAME", type=str, required=False, help="Project slug to update")
    parser.add_argument("--env-file", metavar="FILE", type=str, required=False, help="Read in a file of environment variables")
    parser.add_argument("--with-tags", action="store_true", help="Submit project tags as video captions")
    parser.add_argument("--queue-build", action="store_true", help="Queue a new video build using current settings")
    args = parser.parse_args()

    # Determine project path
    if args.path:
        project_path = os.path.abspath(args.path)
    else:
        project_path = os.path.abspath('.')

    if args.env_file:
        try:
            parse_env_file(args.env_file)
        except FileNotFoundError:
            print(f"** ERROR: Environment file not found: {args.env_file}")
            sys.exit(1)

    try:
        # Server host (http://...)
        host = args.host
        if not host:
            host = get_from_env("GOURCE_HOST", default=DEFAULT_HOST,
                                message="Required variable: GOURCE_HOST or --host")
        # REST API token
        token = args.token
        if not token:
            token = get_from_env("GOURCE_API_TOKEN", default=DEFAULT_API_TOKEN,
                                 message="Required variable: GOURCE_API_TOKEN or --token")
        project_id = None
        project_slug = None
        if args.project_id:
            project_id = args.project_id
        elif args.project_slug:
            project_slug = args.project_slug
        else:
            project_id = get_from_env("GOURCE_PROJECT_ID", required=False, default=DEFAULT_PROJECT_ID)
            if project_id is None:
                project_slug = get_from_env("GOURCE_PROJECT_SLUG", required=False, default=DEFAULT_PROJECT_SLUG)
            else:
                try:
                    project_id = int(project_id)
                except (TypeError, ValueError) as e:
                    raise ValueError(f"Invalid project ID: {project_id}")
        if not project_id and not project_slug:
            print("Error: Must provide either '--project-id' or '--project-slug' identifier", file=sys.stderr)
            sys.exit(1)
    except Exception as e:
        print("Error: {0}".format(str(e)), file=sys.stderr)
        sys.exit(1)

    # Main script
    main_kwargs = {
        "host": host,
        "project_path": project_path,
        "token": token,
    }
    if project_id:
        main_kwargs['project_id'] = project_id
    else:
        main_kwargs['project_slug'] = project_slug
    if args.with_tags:
        main_kwargs['submit_tags'] = True
    if args.queue_build:
        main_kwargs['queue_build'] = True

    main(**main_kwargs)
