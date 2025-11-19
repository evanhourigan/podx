"""
PodX API Client Example - Python

This example demonstrates how to interact with the PodX API Server using Python's requests library.

Features demonstrated:
- File upload
- Job creation
- Real-time progress streaming (SSE)
- Job status checking
- Result retrieval
- Error handling

Requirements:
    pip install requests

Usage:
    python examples/python_client.py
"""

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

import requests


class PodXClient:
    """Python client for PodX API Server."""

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        api_key: Optional[str] = None,
    ):
        """Initialize the PodX client.

        Args:
            base_url: Base URL of the PodX server
            api_key: Optional API key for authentication
        """
        self.base_url = base_url.rstrip("/")
        self.headers = {}
        if api_key:
            self.headers["X-API-Key"] = api_key

    def health_check(self) -> Dict[str, Any]:
        """Check server health.

        Returns:
            Health check response
        """
        response = requests.get(f"{self.base_url}/health")
        response.raise_for_status()
        return response.json()

    def upload_file(self, file_path: str) -> str:
        """Upload an audio file.

        Args:
            file_path: Path to audio file

        Returns:
            Upload ID
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        with open(file_path, "rb") as f:
            files = {"file": (file_path.name, f, "audio/mpeg")}
            response = requests.post(
                f"{self.base_url}/upload",
                files=files,
                headers=self.headers,
            )
            response.raise_for_status()

        data = response.json()
        print(f"✓ Uploaded: {file_path.name} ({data['size_mb']:.1f} MB)")
        return data["upload_id"]

    def create_job(
        self,
        upload_id: Optional[str] = None,
        url: Optional[str] = None,
        profile: str = "quick",
    ) -> str:
        """Create a processing job.

        Args:
            upload_id: ID of uploaded file (optional)
            url: URL to podcast episode (optional)
            profile: Processing profile (quick, medium, full, hq)

        Returns:
            Job ID
        """
        if not upload_id and not url:
            raise ValueError("Must provide either upload_id or url")

        payload = {"profile": profile}
        if upload_id:
            payload["upload_id"] = upload_id
        if url:
            payload["url"] = url

        response = requests.post(
            f"{self.base_url}/jobs",
            json=payload,
            headers=self.headers,
        )
        response.raise_for_status()

        data = response.json()
        print(f"✓ Job created: {data['job_id']}")
        return data["job_id"]

    def get_job(self, job_id: str) -> Dict[str, Any]:
        """Get job status and details.

        Args:
            job_id: Job ID

        Returns:
            Job details
        """
        response = requests.get(
            f"{self.base_url}/jobs/{job_id}",
            headers=self.headers,
        )
        response.raise_for_status()
        return response.json()

    def stream_progress(self, job_id: str):
        """Stream real-time job progress via Server-Sent Events.

        Args:
            job_id: Job ID

        Yields:
            Progress updates
        """
        url = f"{self.base_url}/jobs/{job_id}/stream"
        response = requests.get(
            url,
            headers=self.headers,
            stream=True,
        )
        response.raise_for_status()

        print(f"📡 Streaming progress for job {job_id}...")

        for line in response.iter_lines():
            if not line:
                continue

            line = line.decode("utf-8")

            # Skip comment lines
            if line.startswith(":"):
                continue

            # Parse SSE data
            if line.startswith("data: "):
                data = json.loads(line[6:])
                yield data

                # Print progress update
                if data["status"] == "in_progress":
                    step = data.get("current_step", "processing")
                    progress = data.get("progress", 0)
                    print(f"  [{progress:3d}%] {step}")

                elif data["status"] == "completed":
                    print("✓ Job completed!")

                elif data["status"] == "failed":
                    print(f"✗ Job failed: {data.get('error', 'Unknown error')}")

                # Stop streaming when job is done
                if data["status"] in ("completed", "failed"):
                    break

    def wait_for_job(self, job_id: str, check_interval: int = 5) -> Dict[str, Any]:
        """Wait for a job to complete (polling).

        Args:
            job_id: Job ID
            check_interval: Seconds between status checks

        Returns:
            Final job details
        """
        print(f"⏳ Waiting for job {job_id}...")

        while True:
            job = self.get_job(job_id)
            status = job["status"]

            if status == "completed":
                print("✓ Job completed!")
                return job

            elif status == "failed":
                error = job.get("error", "Unknown error")
                print(f"✗ Job failed: {error}")
                raise RuntimeError(f"Job failed: {error}")

            elif status in ("pending", "in_progress"):
                progress = job.get("progress", 0)
                step = job.get("current_step", "processing")
                print(f"  [{progress:3d}%] {step}")
                time.sleep(check_interval)

            else:
                print(f"  Unknown status: {status}")
                time.sleep(check_interval)

    def list_jobs(self, limit: int = 10) -> Dict[str, Any]:
        """List recent jobs.

        Args:
            limit: Maximum number of jobs to return

        Returns:
            List of jobs
        """
        response = requests.get(
            f"{self.base_url}/jobs",
            params={"limit": limit},
            headers=self.headers,
        )
        response.raise_for_status()
        return response.json()


# Example usage
def main():
    """Example workflow: upload file, create job, stream progress."""
    # Initialize client
    client = PodXClient(
        base_url="http://localhost:8000",
        api_key=None,  # Set if API key authentication is enabled
    )

    # Check server health
    print("1. Checking server health...")
    health = client.health_check()
    print(f"   Server status: {health['status']}")
    print(f"   Version: {health['version']}")
    print()

    # Example 1: Process from URL
    print("2. Creating job from URL...")
    job_id = client.create_job(
        url="https://example.com/podcast.mp3",
        profile="quick",
    )
    print()

    # Example 2: Upload file and create job
    # print("2. Uploading audio file...")
    # upload_id = client.upload_file("path/to/your/audio.mp3")
    # print()
    #
    # print("3. Creating processing job...")
    # job_id = client.create_job(upload_id=upload_id, profile="quick")
    # print()

    # Example 3a: Stream real-time progress (recommended)
    print("3a. Streaming real-time progress...")
    try:
        for update in client.stream_progress(job_id):
            # Progress updates are printed automatically
            # You can also handle them here
            pass
    except Exception as e:
        print(f"Error streaming progress: {e}")
    print()

    # Example 3b: Poll for completion (alternative)
    # print("3b. Polling for job completion...")
    # job = client.wait_for_job(job_id, check_interval=5)
    # print()

    # Get final job details
    print("4. Fetching job details...")
    job = client.get_job(job_id)
    print(f"   Status: {job['status']}")
    print(f"   Profile: {job['profile']}")
    if job.get("result"):
        print(f"   Result: {job['result']}")
    print()

    # List recent jobs
    print("5. Listing recent jobs...")
    jobs = client.list_jobs(limit=5)
    print(f"   Found {len(jobs['jobs'])} jobs:")
    for j in jobs["jobs"]:
        print(f"     - {j['id']}: {j['status']} ({j['profile']})")
    print()

    print("✓ Example completed!")


if __name__ == "__main__":
    main()
