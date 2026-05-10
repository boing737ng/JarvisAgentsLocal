"""Docker sandbox execution tool.
Runs Python code in an isolated Docker container with no network,
limited RAM/CPU, and read-only filesystem.
"""
from __future__ import annotations

import io
import logging
import os
import tarfile
import tempfile
import time
from pathlib import Path
from typing import Any, Dict

import docker
from docker.errors import DockerException, ImageNotFound

from jarvis.core.config import get_settings

logger = logging.getLogger(__name__)

_docker_client: docker.DockerClient | None = None


def _get_client() -> docker.DockerClient:
    global _docker_client
    if _docker_client is None:
        _docker_client = docker.from_env()
    return _docker_client


def ensure_sandbox_image() -> bool:
    """Build the sandbox Docker image if it doesn't exist."""
    settings = get_settings()
    client = _get_client()
    image_name = settings.docker.sandbox_image

    try:
        client.images.get(image_name)
        logger.debug("[docker] Sandbox image exists: %s", image_name)
        return True
    except ImageNotFound:
        pass

    dockerfile_path = Path(__file__).parent.parent.parent / settings.docker.sandbox_dockerfile
    if not dockerfile_path.exists():
        logger.error("[docker] Dockerfile not found: %s", dockerfile_path)
        return False

    logger.info("[docker] Building sandbox image %s ...", image_name)
    try:
        client.images.build(
            path=str(dockerfile_path.parent),
            dockerfile=dockerfile_path.name,
            tag=image_name,
            rm=True,
        )
        logger.info("[docker] Sandbox image built successfully")
        return True
    except Exception as e:
        logger.error("[docker] Failed to build sandbox image: %s", e)
        return False


def run_python_in_sandbox(
    code: str,
    timeout: int | None = None,
    mem_limit: str | None = None,
) -> Dict[str, Any]:
    """
    Execute Python code in an isolated Docker container.

    Returns:
        {
            "exit_code": int,
            "stdout": str,
            "stderr": str,
            "duration": float,
            "success": bool,
        }
    """
    settings = get_settings()
    timeout = timeout or settings.docker.timeout_seconds
    mem_limit = mem_limit or settings.docker.mem_limit

    if not ensure_sandbox_image():
        return {
            "exit_code": -1,
            "stdout": "",
            "stderr": "Failed to prepare sandbox Docker image",
            "duration": 0.0,
            "success": False,
        }

    client = _get_client()
    workspace_path = settings.workspace_path()
    workspace_path.mkdir(parents=True, exist_ok=True)

    start_time = time.time()
    container = None

    try:
        container = client.containers.run(
            image=settings.docker.sandbox_image,
            command=["python", "-c", code],
            detach=True,
            network_disabled=True,
            mem_limit=mem_limit,
            cpu_quota=settings.docker.cpu_quota,
            read_only=True,
            tmpfs={"/tmp": "size=256m"},
            volumes={
                str(workspace_path.resolve()): {
                    "bind": settings.docker.workspace_mount,
                    "mode": "rw",
                }
            },
            remove=False,
        )

        # Wait with timeout
        try:
            result = container.wait(timeout=timeout)
            exit_code = result.get("StatusCode", -1)
        except Exception:
            logger.warning("[docker] Container timed out, killing...")
            try:
                container.kill()
            except Exception:
                pass
            exit_code = -1

        logs = container.logs(stdout=True, stderr=True)
        stdout_bytes = container.logs(stdout=True, stderr=False)
        stderr_bytes = container.logs(stdout=False, stderr=True)

        duration = time.time() - start_time

        return {
            "exit_code": exit_code,
            "stdout": stdout_bytes.decode("utf-8", errors="replace"),
            "stderr": stderr_bytes.decode("utf-8", errors="replace"),
            "duration": round(duration, 2),
            "success": exit_code == 0,
        }

    except DockerException as e:
        duration = time.time() - start_time
        logger.error("[docker] Container run failed: %s", e)
        return {
            "exit_code": -1,
            "stdout": "",
            "stderr": str(e),
            "duration": round(duration, 2),
            "success": False,
        }
    finally:
        if container:
            try:
                container.remove(force=True)
            except Exception:
                pass
