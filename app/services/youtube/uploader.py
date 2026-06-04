from app.models.content import VideoJob


class YouTubeUploader:
    def upload_private(self, job: VideoJob, metadata: dict[str, object], thumbnail_path: str) -> dict[str, object]:
        try:
            from googleapiclient.discovery import build  # type: ignore  # noqa: F401
        except Exception as exc:
            raise RuntimeError("YouTube upload dependencies are not installed. Install google-api-python-client and google-auth-oauthlib.") from exc
        raise RuntimeError("Real YouTube upload client is not configured in this environment.")


class FakeYouTubeUploader:
    def upload_private(self, job: VideoJob, metadata: dict[str, object], thumbnail_path: str) -> dict[str, object]:
        video_id = f"private_mock_{job.id}"
        return {
            "youtube_video_id": video_id,
            "youtube_upload_url": f"https://studio.youtube.com/video/{video_id}/edit",
            "thumbnail_uploaded": bool(thumbnail_path),
        }
