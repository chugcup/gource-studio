#!/usr/bin/env python3

#############################################################################
# Generate Gource log from current project and upload to server.
#############################################################################

import argparse
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


def main(host, token, project_path, project_id=None, project_slug=None):
    if not os.path.isdir(project_path):
        raise RuntimeError(f"Path not valid directory: {project_path}")
    project_type = determine_project_type(project_path)

    # Validate host
    o = urllib.parse.urlparse(host)
    server_host = f"{o.scheme}://{o.netloc}"

    # Determine latest commit details (SHA1 hash, commit subject)
    author_timestamp = None
    commit_hash = None
    commit_subject = None
    if project_type == 'git':
        author_timestamp, commit_hash, commit_subject = get_latest_git_commit(project_path)
    elif project_type == 'mercurial':
        author_timestamp, commit_hash, commit_subject = get_latest_mercurial_commit(project_path)
    print(author_timestamp)
    print(commit_hash)
    print(commit_subject)

    gource_path = get_gource_path()
    # Generate log in temp directory
    output_log = tempfile.mkstemp(suffix=".log", prefix="gource_")[1]
    print(output_log)
    try:
        print("Generating Gource log...", end='')
        sys.stdout.flush()
        generate_log(project_path, output_log)
        print("")
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

        print("Sending update to server...", end='')
        sys.stdout.flush()
        # Submit using Token authentication
        req = urllib.request.Request(log_url, method="PUT", data=json.dumps(put_data).encode('utf-8'), headers={
            'Content-Type': 'application/json',
            'Authorization': f'Token {token}'
        })
        res = urllib.request.urlopen(req)
        print("")
        if res.status not in [200, 201]:
            print(f"ERROR: Unexpected HTTP response: {res.status} {res.reason}", file=sys.stderr)
            return
        #shutil.copyfile(output_log, f'./{os.path.basename(output_log)}')
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

def get_from_env(name, required=True, message=None):
    "Fetch an environment variable by name"
    value = os.environ.get(name, None)
    if value is None and required:
        if not message:
            message = f"Missing required option: {name}"
        raise RuntimeError(message)
    return value


if __name__ == "__main__":
    parser = argparse.ArgumentParser("Generate Gource log and submit to Gource Studio server.")
    parser.add_argument("path", metavar="PROJECT_DIR", nargs='?', help="Root directory path (default=cwd)")
    parser.add_argument("--host", metavar="HOST", type=str, help="Full URL to Gource Studio server")
    parser.add_argument("--token", metavar="TOKEN", type=str, help="API Token used to authenticate upload")
    group1 = parser.add_mutually_exclusive_group()
    group1.add_argument("--project-id", metavar="ID", type=int, help="Project ID to update")
    group1.add_argument("--project-slug", metavar="NAME", type=str, help="Project slug to update")
    args = parser.parse_args()

    # Determine project path
    if args.path:
        project_path = os.path.abspath(args.path)
    else:
        project_path = os.path.abspath('.')
    print(project_path)

    try:
        # Server host (http://...)
        host = args.host
        if not host:
            host = get_from_env("GOURCE_HOST", message="Required argument: --host")
        # REST API token
        token = args.token
        if not token:
            token = get_from_env("GOURCE_API_TOKEN", message="Required argument: --token")
        project_id = None
        project_slug = None
        if args.project_id:
            project_id = args.project_id
        elif args.project_slug:
            project_slug = args.project_slug
        else:
            project_id = get_from_env("GOURCE_PROJECT_ID", required=False)
            if project_id is None:
                project_slug = get_from_env("GOURCE_PROJECT_SLUG", required=False)
            else:
                project_id = int(project_id)
        if not project_id and not project_slug:
            print("Error: Must provide either '--project-id' or '--project-slug' identifier", file=sys.stderr)
            sys.exit(1)
    except RuntimeError as e:
        print("Error: {0}".format(str(e)), file=sys.stderr)
        sys.exit(1)

    # Main script
    main_kwargs = {
        "host": host,
        "project_path": project_path,
        "token": token
    }
    if project_id:
        main_kwargs['project_id'] = project_id
    else:
        main_kwargs['project_slug'] = project_slug
    main(**main_kwargs)
