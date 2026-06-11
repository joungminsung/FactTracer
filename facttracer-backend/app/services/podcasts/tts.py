from __future__ import annotations

import io
import re
import wave
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from openai import OpenAI
from sqlalchemy.orm import Session

from app import models
from app.core.config import get_settings
from app.services.admin.settings import get_effective_setting
from app.services.files.storage import store_binary_file


VOICE_BY_SPEAKER = {
    "anchor": "marin",
    "analyst": "cedar",
    "reporter": "coral",
}

VOICE_FALLBACKS = {
    "marin": "alloy",
    "cedar": "verse",
    "coral": "nova",
}

MIME_BY_FORMAT = {
    "mp3": "audio/mpeg",
    "wav": "audio/wav",
}

MAX_TTS_INPUT_CHARS = 4096
MAX_TTS_ATTEMPTS = 2
OPENAI_KEY_PATTERN = re.compile(r"sk-[A-Za-z0-9_*\\-]{8,}")


def parse_pronunciation_lexicon(value: Any) -> dict[str, str]:
    if not value:
        return {}
    if isinstance(value, dict):
        return {
            str(source).strip(): str(target).strip()
            for source, target in value.items()
            if str(source).strip() and str(target).strip()
        }
    rows = re.split(r"[\n,]+", str(value))
    lexicon: dict[str, str] = {}
    for row in rows:
        if "=" not in row:
            continue
        source, target = row.split("=", 1)
        source = source.strip()
        target = target.strip()
        if source and target:
            lexicon[source] = target
    return lexicon


def safe_tts_error_message(exc: Exception) -> str:
    raw = str(exc)
    lowered = raw.lower()
    if "invalid_api_key" in lowered or "incorrect api key" in lowered:
        return "OpenAI TTS authentication failed: invalid_api_key"
    redacted = OPENAI_KEY_PATTERN.sub("sk-<redacted>", raw)
    return redacted[:500]


class OpenAITTSEpisodeRenderer:
    def __init__(self, db: Session | None = None) -> None:
        self.settings = get_settings()
        self.ai_processing_enabled = bool(get_effective_setting(db, "ai_processing_enabled"))
        self.tts_enabled = bool(get_effective_setting(db, "podcast_tts_enabled", True))
        self.api_key = get_effective_setting(db, "openai_api_key")
        self.model = str(get_effective_setting(db, "openai_tts_model") or "gpt-4o-mini-tts")
        self.response_format = str(get_effective_setting(db, "openai_tts_response_format") or "wav")
        self.speed = float(get_effective_setting(db, "openai_tts_speed") or 1.0)
        self.timeout_seconds = int(get_effective_setting(db, "openai_tts_timeout_seconds") or 120)
        self.pronunciation_lexicon = parse_pronunciation_lexicon(
            get_effective_setting(db, "podcast_tts_pronunciation_lexicon", ""),
        )
        self._client: OpenAI | None = None

    @property
    def enabled(self) -> bool:
        return bool(self.ai_processing_enabled and self.tts_enabled and self.api_key)

    @property
    def client(self) -> OpenAI:
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured")
        if self._client is None:
            self._client = OpenAI(api_key=self.api_key, timeout=self.timeout_seconds)
        return self._client

    def render_episode(self, db: Session, *, episode: models.PodcastEpisode, force: bool = False) -> models.PodcastEpisode:
        if episode.audio_url and not force:
            return episode
        if not self.enabled:
            self._mark_unconfigured(episode)
            db.flush()
            return episode

        script = [segment for segment in (episode.script_json or []) if isinstance(segment, dict)]
        if not script:
            self._merge_generation_json(
                episode,
                {
                    "ttsError": "script is empty",
                    "ttsStatus": "failed",
                    "ttsProvider": "openai",
                },
            )
            db.flush()
            return episode

        attempt_logs: list[dict[str, Any]] = []
        try:
            rendered_segments = [
                self._speech_bytes_with_retries(
                    attempt_logs=attempt_logs,
                    input_text=self._segment_text(segment),
                    instructions=self._segment_instructions(segment, episode),
                    segment_index=index,
                    voice=self._voice_for_segment(segment),
                )
                for index, segment in enumerate(script)
            ]
        except Exception as exc:
            safe_error = safe_tts_error_message(exc)
            self._merge_generation_json(
                episode,
                {
                    "ttsAttemptCount": len(attempt_logs),
                    "ttsAttempts": attempt_logs,
                    "ttsError": safe_error,
                    "ttsErrorType": type(exc).__name__,
                    "ttsModel": self.model,
                    "ttsProvider": "openai",
                    "ttsResponseFormat": self.response_format,
                    "ttsStatus": "failed",
                },
            )
            episode.updated_at = models.now_utc()
            db.flush()
            raise
        audio_bytes, duration_seconds = self._combine_audio(rendered_segments)
        suffix = f".{self.response_format if self.response_format in MIME_BY_FORMAT else 'mp3'}"
        storage_url, byte_count = store_binary_file(
            data=audio_bytes,
            directory="podcasts",
            file_id=episode.id,
            suffix=suffix,
        )
        episode.audio_url = storage_url
        if duration_seconds:
            episode.duration_seconds = duration_seconds
        episode.updated_at = models.now_utc()
        self._merge_generation_json(
            episode,
            {
                "audioBytes": byte_count,
                "audioMimeType": MIME_BY_FORMAT.get(self.response_format, "audio/mpeg"),
                "audioStoragePath": storage_url,
                "renderedAt": models.now_utc().isoformat(),
                "ttsModel": self.model,
                "ttsProvider": "openai",
                "ttsResponseFormat": self.response_format,
                "ttsAttemptCount": len(attempt_logs),
                "ttsAttempts": attempt_logs,
                "ttsSegmentCount": len(rendered_segments),
                "ttsStatus": "completed",
                "ttsPronunciationTerms": sorted(self.pronunciation_lexicon.keys()),
                "voiceMap": {
                    segment.get("speakerId"): self._voice_for_segment(segment)
                    for segment in script
                    if segment.get("speakerId")
                },
            },
        )
        db.flush()
        return episode

    def _speech_bytes_with_retries(
        self,
        *,
        attempt_logs: list[dict[str, Any]],
        input_text: str,
        instructions: str,
        segment_index: int,
        voice: str,
    ) -> bytes:
        last_error: Exception | None = None
        for attempt in range(1, MAX_TTS_ATTEMPTS + 1):
            try:
                audio = self._speech_bytes(
                    input_text=input_text,
                    instructions=instructions,
                    voice=voice,
                )
                attempt_logs.append(
                    {
                        "attempt": attempt,
                        "bytes": len(audio),
                        "segmentIndex": segment_index,
                        "status": "completed",
                        "voice": voice,
                    },
                )
                return audio
            except Exception as exc:
                last_error = exc
                attempt_logs.append(
                    {
                        "attempt": attempt,
                        "error": safe_tts_error_message(exc),
                        "errorType": type(exc).__name__,
                        "segmentIndex": segment_index,
                        "status": "failed",
                        "voice": voice,
                    },
                )
        if last_error:
            raise last_error
        raise RuntimeError("OpenAI TTS failed without an error")

    def _speech_bytes(self, *, input_text: str, instructions: str, voice: str) -> bytes:
        suffix = f".{self.response_format if self.response_format in MIME_BY_FORMAT else 'mp3'}"
        with NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            target = Path(tmp.name)
        try:
            with self.client.audio.speech.with_streaming_response.create(
                input=input_text[:MAX_TTS_INPUT_CHARS],
                instructions=instructions[:900],
                model=self.model,
                response_format=self.response_format,
                speed=self.speed,
                voice=voice,
            ) as response:
                response.stream_to_file(target)
            return target.read_bytes()
        finally:
            target.unlink(missing_ok=True)

    def _combine_audio(self, rendered_segments: list[bytes]) -> tuple[bytes, int]:
        if not rendered_segments:
            return b"", 0
        if self.response_format == "wav":
            return self._combine_wav(rendered_segments)
        return b"".join(rendered_segments), 0

    def _combine_wav(self, rendered_segments: list[bytes]) -> tuple[bytes, int]:
        output = io.BytesIO()
        params = None
        total_frames = 0
        with wave.open(output, "wb") as writer:
            for data in rendered_segments:
                with wave.open(io.BytesIO(data), "rb") as reader:
                    current_params = reader.getparams()
                    comparable = current_params[:3]
                    if params is None:
                        params = current_params
                        writer.setnchannels(current_params.nchannels)
                        writer.setsampwidth(current_params.sampwidth)
                        writer.setframerate(current_params.framerate)
                    elif comparable != params[:3]:
                        raise ValueError("TTS WAV segments have incompatible audio parameters")
                    frames = reader.readframes(current_params.nframes)
                    bytes_per_frame = current_params.nchannels * current_params.sampwidth
                    if bytes_per_frame:
                        total_frames += len(frames) // bytes_per_frame
                    writer.writeframes(frames)
        duration = int(round(total_frames / params.framerate)) if params else 0
        return output.getvalue(), duration

    def _mark_unconfigured(self, episode: models.PodcastEpisode) -> None:
        reason = "OPENAI_API_KEY is not configured" if not self.api_key else "podcast TTS is disabled"
        self._merge_generation_json(
            episode,
            {
                "ttsError": reason,
                "ttsModel": self.model,
                "ttsProvider": "openai",
                "ttsResponseFormat": self.response_format,
                "ttsStatus": "skipped_unconfigured",
            },
        )
        episode.updated_at = models.now_utc()

    def _merge_generation_json(self, episode: models.PodcastEpisode, updates: dict[str, Any]) -> None:
        episode.generation_json = {**(episode.generation_json or {}), **updates}

    def _segment_text(self, segment: dict[str, Any]) -> str:
        text = " ".join(str(segment.get("text") or "").split())
        for source, target in sorted(self.pronunciation_lexicon.items(), key=lambda item: len(item[0]), reverse=True):
            text = text.replace(source, target)
        return text

    def _segment_instructions(self, segment: dict[str, Any], episode: models.PodcastEpisode) -> str:
        role = str(segment.get("role") or "진행")
        speaker_name = str(segment.get("speakerName") or "")
        return (
            "한국어 뉴스 팟캐스트 톤으로 말하세요. "
            "사실과 추정은 분리하고, 선정적인 표현 없이 차분하게 전달하세요. "
            f"화자는 {speaker_name}이며 역할은 {role}입니다. "
            f"회차 주제는 {episode.title}입니다."
        )

    def _voice_for_segment(self, segment: dict[str, Any]) -> str:
        speaker_id = str(segment.get("speakerId") or "anchor")
        preferred = VOICE_BY_SPEAKER.get(speaker_id, "marin")
        if self.model.startswith("tts-"):
            return VOICE_FALLBACKS.get(preferred, preferred)
        return preferred


def episode_audio_mime_type(episode: models.PodcastEpisode) -> str:
    generation = episode.generation_json if isinstance(episode.generation_json, dict) else {}
    return str(generation.get("audioMimeType") or MIME_BY_FORMAT.get(str(generation.get("ttsResponseFormat") or "wav"), "audio/wav"))


def public_episode_audio_url(episode: models.PodcastEpisode) -> str | None:
    if not episode.audio_url:
        return None
    return f"/v1/podcasts/{episode.id}/audio"


def render_episode_audio(
    db: Session,
    *,
    episode: models.PodcastEpisode,
    force: bool = False,
) -> models.PodcastEpisode:
    return OpenAITTSEpisodeRenderer(db).render_episode(db, episode=episode, force=force)
