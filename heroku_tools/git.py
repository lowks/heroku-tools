# -*- coding: utf-8 -*-
"""Git related commands.

Git module uses the Envoy library to run git commands
against a git repo as configured in settings.SETTINGS
with the WORK_DIR and GIT_DIR values.

"""
import os
import envoy

from heroku_tools.settings import SETTINGS

# location of the website git repo directory
WORK_DIR = SETTINGS['git_work_dir']
GIT_DIR = os.path.join(WORK_DIR, '.git')
GIT_CMD_PREFIX = "git --git-dir=%s --work-tree=%s " % (GIT_DIR, WORK_DIR)


def run_git_cmd(command):
    """Run specified git command.

    This function is used to ensure that all git commands are run against
    the correct repository by including the the --git-dir and --work-tree
    options. This is required as we are running the commands outside of
    the target repo directory.

    Args:
        command: the command to run - without the 'git ' prefix, e.g.
            "status", "log --oneline", etc.

    Returns the output of the command as a string.

    """
    cmd = GIT_CMD_PREFIX + command
    r = envoy.run(cmd)
    if r.status_code > 0:
        raise Exception(
            u"Error running git command '%s': %s"
            % (cmd, r.std_err)
        )
    return r.std_out


def get_remote_url(app_name):
    """Return the git remote address on Heroku."""
    return "git@heroku.com:%s.git" % app_name


def get_editor():
    """Return the configured editor value.

    Looks first in git.config, then SETTINGS

    Raise an Exception if no editor is configured.

    """
    editor = (
        run_git_cmd('config --get core.editor') or
        SETTINGS.get('editor')
    )
    if editor is None:
        raise Exception(
            "No editor configured in git config, "
            "$EDITOR or $VISUAL."
        )

    return editor


def push(remote, local_branch, remote_branch="master", force=False):
    """Push a branch to a remote repo."""
    if force:
        run_git_cmd("push %s %s:%s -f" % (remote, local_branch, remote_branch))
    else:
        run_git_cmd("push %s %s:%s" % (remote, local_branch, remote_branch))


def get_current_branch():
    """Return the current branch name (from GIT_DIR)."""
    return run_git_cmd("rev-parse --abbrev-ref HEAD")


def get_branch_head(branch):
    """Return the hash of the latest commit on a given branch."""
    # cast to str as passing unicode to git commands causes them to fail
    return run_git_cmd("rev-parse %s" % branch)[:7]


def get_commits(commit_from, commit_to):
    """Return the oneline format history between two commits.

    Args:
        commit_from: the commit hash of the earlier commit.
        commit_to: the commit hash of the later commit, defaults to HEAD.

    Returns a list of 2-tuples, each containing the commit hash, and the commit
    message.

    e.g. if the commit log looks like this:

        81a5ea8 Fix for failing tests.
        62d49e9 Refactoring of conversations.

    The return value is:

        [
            ('81a5ea8', 'Fix for failing tests.'),
            ('62d49e9', Refactoring of conversations.)
        ]

    """
    command = "log --oneline --no-merges %s..%s" % (commit_from, commit_to)
    raw = run_git_cmd(command)
    lines = raw.lstrip().rstrip().split('\n')
    return [(l[:7], l[8:]) for l in lines if l != '']


def get_files(commit_from, commit_to):
    """Return the names of the files that have changed between two commits.

    Args:
        commit_from: the first commit - can be a commit hash or a tag.
        commit_to: the last commit - can be a commit hash or a tag.

    Returns a list of fully qualified filenames.

    """
    command = "diff --name-only %s..%s" % (commit_from, commit_to)
    raw = run_git_cmd(command)
    files = raw.lstrip().rstrip().split('\n')
    files.sort()
    # strip empty strings
    return [f for f in files if f != '']


def apply_tag(commit, tag, message):
    """Apply a tag to a given git commit."""
    command = "tag -a %s -m  '%s' %s" % (tag, message, commit)
    run_git_cmd(command)
