"""Git utilities for extracting commit messages and repository info."""

import subprocess
from pathlib import Path
from typing import Optional


class GitError(Exception):
    """Raised when git operations fail."""

    pass


def is_git_repo(directory: Path) -> bool:
    """Check if directory is a git repository.

    Args:
        directory: Directory to check.

    Returns:
        True if directory is a git repository.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=directory,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


def get_latest_commit_message(
    directory: Path,
    branch: Optional[str] = None,
) -> Optional[str]:
    """Get the latest commit message.

    Args:
        directory: Git repository directory.
        branch: Optional branch name (defaults to current branch).

    Returns:
        Latest commit message or None if not a git repo.
    """
    if not is_git_repo(directory):
        return None

    try:
        cmd = ["git", "log", "-1", "--pretty=%B"]
        if branch:
            cmd.append(branch)

        result = subprocess.run(
            cmd,
            cwd=directory,
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except (subprocess.SubprocessError, FileNotFoundError):
        return None


def get_commit_range_messages(
    directory: Path,
    from_ref: str = "HEAD~1",
    to_ref: str = "HEAD",
) -> list[str]:
    """Get commit messages in a range.

    Args:
        directory: Git repository directory.
        from_ref: Starting reference.
        to_ref: Ending reference.

    Returns:
        List of commit messages.
    """
    if not is_git_repo(directory):
        return []

    try:
        result = subprocess.run(
            ["git", "log", f"{from_ref}..{to_ref}", "--pretty=%B"],
            cwd=directory,
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode == 0:
            # Split by double newline (separates commits)
            messages = [msg.strip() for msg in result.stdout.split("\n\n") if msg.strip()]
            return messages
        return []
    except (subprocess.SubprocessError, FileNotFoundError):
        return []


def get_git_head(directory: Path) -> Optional[str]:
    """Get the current git HEAD commit hash.

    Args:
        directory: Git repository directory.

    Returns:
        Commit hash or None if not a git repo.
    """
    if not is_git_repo(directory):
        return None

    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=directory,
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except (subprocess.SubprocessError, FileNotFoundError):
        return None


def get_git_branch(directory: Path) -> Optional[str]:
    """Get the current git branch name.

    Args:
        directory: Git repository directory.

    Returns:
        Branch name or None if not a git repo or detached HEAD.
    """
    if not is_git_repo(directory):
        return None

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=directory,
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode == 0:
            branch = result.stdout.strip()
            if branch == "HEAD":
                return None  # Detached HEAD
            return branch
        return None
    except (subprocess.SubprocessError, FileNotFoundError):
        return None


def get_changed_files(
    directory: Path,
    from_ref: str = "HEAD~1",
    to_ref: str = "HEAD",
) -> list[str]:
    """Get list of changed files in a commit range.

    Args:
        directory: Git repository directory.
        from_ref: Starting reference.
        to_ref: Ending reference.

    Returns:
        List of changed file paths.
    """
    if not is_git_repo(directory):
        return []

    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", f"{from_ref}..{to_ref}"],
            cwd=directory,
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode == 0:
            return [f.strip() for f in result.stdout.split("\n") if f.strip()]
        return []
    except (subprocess.SubprocessError, FileNotFoundError):
        return []


def get_git_info(directory: Path) -> dict:
    """Get comprehensive git information.

    Args:
        directory: Git repository directory.

    Returns:
        Dictionary with git information.
    """
    return {
        "is_git_repo": is_git_repo(directory),
        "head": get_git_head(directory),
        "branch": get_git_branch(directory),
        "latest_commit": get_latest_commit_message(directory),
    }
