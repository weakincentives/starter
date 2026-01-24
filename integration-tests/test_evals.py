"""Integration tests for trivia agent evals.

Run with:
    make integration-test
"""

from __future__ import annotations

import os
import re
import signal
import socket
import subprocess
import time
from collections.abc import Generator
from pathlib import Path

import pytest


def find_free_port() -> int:
    """Find a free port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        s.listen(1)
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def redis_url() -> Generator[str, None, None]:
    """Start Redis on a random port and yield the URL."""
    port = find_free_port()
    container_name = f"wink-test-redis-{port}"

    # Start Redis container
    result = subprocess.run(
        ["docker", "run", "-d", "--name", container_name, "-p", f"{port}:6379", "redis:7-alpine"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.skip(f"Could not start Redis: {result.stderr}")

    url = f"redis://localhost:{port}"

    # Wait for Redis
    from redis import Redis

    for _ in range(30):
        try:
            Redis.from_url(url).ping()
            break
        except Exception:
            time.sleep(0.1)
    else:
        subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)
        pytest.fail("Redis failed to start")

    yield url

    subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)


@pytest.fixture(scope="module")
def agent(redis_url: str) -> Generator[subprocess.Popen[bytes], None, None]:
    """Start the trivia agent."""
    env = os.environ.copy()
    env["REDIS_URL"] = redis_url

    # Enable debug bundle generation
    project_root = Path(__file__).parent.parent
    env["TRIVIA_DEBUG_BUNDLES_DIR"] = str(project_root / "debug_bundles")

    # Use DEVNULL to prevent blocking on full output buffers
    proc = subprocess.Popen(
        ["uv", "run", "trivia-agent"],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(3)

    if proc.poll() is not None:
        pytest.fail("Agent failed to start")

    yield proc

    proc.send_signal(signal.SIGTERM)
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


def parse_bundle_path(stdout: str) -> str | None:
    """Parse the bundle path from eval output."""
    match = re.search(r"Bundle: (.+\.zip)", stdout)
    return match.group(1) if match else None


def run_eval(redis_url: str, question: str, expected: str) -> subprocess.CompletedProcess[str]:
    """Run an eval."""
    env = os.environ.copy()
    env["REDIS_URL"] = redis_url

    return subprocess.run(
        ["uv", "run", "trivia-dispatch", "--eval", "--question", question, "--expected", expected],
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


@pytest.mark.parametrize(
    "question,expected",
    [
        ("What is the secret number?", "42"),
        ("What is the secret word?", "banana"),
        ("What is the secret color?", "purple"),
        ("What is the magic phrase?", "Open sesame"),
    ],
)
@pytest.mark.flaky(reruns=2)  # Retry up to 2 times due to model non-determinism
def test_eval(agent: subprocess.Popen[bytes], redis_url: str, question: str, expected: str) -> None:
    """Test that evals pass for all secrets.

    Note: These tests may occasionally fail due to LLM non-determinism.
    The @flaky decorator retries failed tests up to 2 times.
    """
    assert agent.poll() is None, "Agent died"

    result = run_eval(redis_url, question, expected)

    # Parse debug bundle path from output for error messages
    bundle = parse_bundle_path(result.stdout)
    bundle_info = f"\nDebug bundle: {bundle}" if bundle else ""

    assert result.returncode == 0, (
        f"Eval failed:\nstdout: {result.stdout}\nstderr: {result.stderr}{bundle_info}"
    )
    assert "PASSED" in result.stdout, f"Expected PASSED in output:\n{result.stdout}{bundle_info}"
