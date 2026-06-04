from pathlib import Path

from app.core.config import get_settings


def youtube_auth_status() -> dict[str, object]:
    settings = get_settings()
    return {
        "client_secret_file": str(settings.youtube_client_secret_file),
        "client_secret_exists": Path(settings.youtube_client_secret_file).exists(),
        "token_file": str(settings.youtube_token_file),
        "token_exists": Path(settings.youtube_token_file).exists(),
        "authenticated": Path(settings.youtube_token_file).exists(),
    }


def run_youtube_auth() -> dict[str, object]:
    status = youtube_auth_status()
    if not status["client_secret_exists"]:
        return {**status, "status": "missing_credentials", "message": "Place OAuth Desktop credentials at YOUTUBE_CLIENT_SECRET_FILE before running auth."}
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore
    except Exception:
        return {**status, "status": "missing_dependency", "message": "Install google-auth-oauthlib to run OAuth auth."}
    settings = get_settings()
    scopes = ["https://www.googleapis.com/auth/youtube.upload"]
    flow = InstalledAppFlow.from_client_secrets_file(str(settings.youtube_client_secret_file), scopes)
    credentials = flow.run_local_server(port=0)
    Path(settings.youtube_token_file).parent.mkdir(parents=True, exist_ok=True)
    Path(settings.youtube_token_file).write_text(credentials.to_json(), encoding="utf-8")
    return {**youtube_auth_status(), "status": "authenticated", "message": "YouTube OAuth token saved locally."}
