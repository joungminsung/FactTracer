"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { usePathname } from "next/navigation";
import { useAuth } from "@/components/auth/auth-provider";
import { PodcastMiniPlayer } from "@/components/podcast/podcast-mini-player";
import { PodcastPlayerSheet } from "@/components/podcast/podcast-player-sheet";
import { getUserActionMessage } from "@/lib/api/messages";
import {
  buildPlayableEpisodeFromSummary,
  buildPodcastAudioUrl,
  getPodcastDetail,
} from "@/lib/api/podcasts";
import { recordAnalyticsEvent } from "@/lib/api/facttracer";
import type {
  PodcastEpisodeDetail,
  PodcastEpisodeSummary,
} from "@/lib/api/types";

type PodcastPlayerContextValue = {
  canPlayAudio: boolean;
  currentTime: number;
  duration: number;
  errorMessage: string | null;
  isBuffering: boolean;
  isExpanded: boolean;
  isLoadingDetail: boolean;
  isPlaying: boolean;
  playbackRate: number;
  queue: PodcastEpisodeSummary[];
  selectedEpisode: PodcastEpisodeDetail | null;
  close: () => void;
  closeSheet: () => void;
  expand: () => void;
  goNext: () => Promise<void>;
  goPrevious: () => void;
  playEpisode: (
    episode: PodcastEpisodeSummary,
    queue?: PodcastEpisodeSummary[],
  ) => Promise<void>;
  seekBy: (seconds: number) => void;
  seekTo: (seconds: number) => void;
  setPlaybackRate: (rate: number) => void;
  togglePlayback: () => Promise<void>;
};

const PodcastPlayerContext = createContext<PodcastPlayerContextValue | null>(
  null,
);

export function PodcastPlayerProvider({ children }: { children: ReactNode }) {
  const { token } = useAuth();
  const pathname = usePathname();
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const lastProgressBucketRef = useRef<number>(-1);
  const [selectedEpisode, setSelectedEpisode] =
    useState<PodcastEpisodeDetail | null>(null);
  const [queue, setQueue] = useState<PodcastEpisodeSummary[]>([]);
  const [history, setHistory] = useState<PodcastEpisodeSummary[]>([]);
  const [isExpanded, setIsExpanded] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isBuffering, setIsBuffering] = useState(false);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [playbackRate, setPlaybackRateState] = useState(1);

  const audioSrc = buildPodcastAudioUrl(selectedEpisode?.audioUrl);
  const canPlayAudio = Boolean(audioSrc);
  const shouldHidePlayer = pathname.startsWith("/admin");

  const recordPodcastEvent = useCallback(
    async (
      eventType: string,
      episode: PodcastEpisodeDetail | PodcastEpisodeSummary,
      metadata: Record<string, unknown> = {},
    ) => {
      try {
        await recordAnalyticsEvent(
          {
            eventType,
            issueId: episode.issueId ?? null,
            metadata: {
              episodeId: episode.id,
              podcastCategory: episode.category,
              podcastFormat: episode.format,
              ...metadata,
            },
          },
          token,
        );
      } catch {
        // Analytics must never block playback.
      }
    },
    [token],
  );

  const playEpisode = useCallback(
    async (
      episode: PodcastEpisodeSummary,
      nextQueue: PodcastEpisodeSummary[] = [],
    ) => {
      const previousEpisode = selectedEpisode;

      setIsLoadingDetail(true);
      setErrorMessage(null);
      setSelectedEpisode(buildPlayableEpisodeFromSummary(episode));
      setQueue(nextQueue.filter((item) => item.id !== episode.id));
      setCurrentTime(0);
      setDuration(episode.durationSeconds);
      lastProgressBucketRef.current = -1;

      try {
        const detail = await getPodcastDetail(episode.id, token);
        setSelectedEpisode(detail.episode);
        setQueue(
          (detail.nextQueue.length > 0 ? detail.nextQueue : nextQueue).filter(
            (item) => item.id !== episode.id,
          ),
        );
        if (previousEpisode && previousEpisode.id !== episode.id) {
          setHistory((current) => [
            previousEpisode,
            ...current.filter((item) => item.id !== previousEpisode.id),
          ]);
        }
        await recordPodcastEvent("podcast_play_start", detail.episode);
        setIsPlaying(Boolean(detail.episode.audioUrl));
      } catch (error) {
        setIsPlaying(false);
        setErrorMessage(
          getUserActionMessage(error, "팟캐스트 상세 정보를 불러오지 못했습니다."),
        );
      } finally {
        setIsLoadingDetail(false);
      }
    },
    [recordPodcastEvent, selectedEpisode, token],
  );

  const close = useCallback(() => {
    audioRef.current?.pause();
    setSelectedEpisode(null);
    setQueue([]);
    setHistory([]);
    setIsExpanded(false);
    setIsPlaying(false);
    setErrorMessage(null);
    setCurrentTime(0);
    setDuration(0);
  }, []);

  const togglePlayback = useCallback(async () => {
    if (!selectedEpisode) return;

    if (!audioRef.current || !canPlayAudio) {
      setErrorMessage("아직 재생 가능한 오디오가 없습니다.");
      return;
    }

    if (isPlaying) {
      audioRef.current.pause();
      setIsPlaying(false);
      await recordPodcastEvent("podcast_pause", selectedEpisode, {
        currentTime,
      });
      return;
    }

    try {
      await audioRef.current.play();
      setIsPlaying(true);
      await recordPodcastEvent("podcast_resume", selectedEpisode, {
        currentTime,
      });
    } catch {
      setIsPlaying(false);
      setErrorMessage("브라우저에서 오디오 재생을 시작하지 못했습니다.");
    }
  }, [
    canPlayAudio,
    currentTime,
    isPlaying,
    recordPodcastEvent,
    selectedEpisode,
  ]);

  const seekTo = useCallback((seconds: number) => {
    if (!audioRef.current) return;
    const bounded = Math.max(0, Math.min(seconds, duration || seconds));
    audioRef.current.currentTime = bounded;
    setCurrentTime(bounded);
  }, [duration]);

  const seekBy = useCallback(
    (seconds: number) => {
      seekTo((audioRef.current?.currentTime ?? currentTime) + seconds);
    },
    [currentTime, seekTo],
  );

  const goNext = useCallback(async () => {
    const nextEpisode = queue[0];
    if (!nextEpisode) return;
    if (selectedEpisode && (!duration || currentTime < duration - 2)) {
      await recordPodcastEvent("podcast_skip", selectedEpisode, {
        currentTime,
        duration,
      });
    }
    await playEpisode(nextEpisode, queue.slice(1));
  }, [
    currentTime,
    duration,
    playEpisode,
    queue,
    recordPodcastEvent,
    selectedEpisode,
  ]);

  const goPrevious = useCallback(() => {
    const previousEpisode = history[0];
    if (!previousEpisode) {
      seekTo(0);
      return;
    }
    void playEpisode(previousEpisode, [
      ...(selectedEpisode ? [selectedEpisode] : []),
      ...queue,
    ]);
    setHistory((current) => current.slice(1));
  }, [history, playEpisode, queue, seekTo, selectedEpisode]);

  const setPlaybackRate = useCallback((rate: number) => {
    setPlaybackRateState(rate);
    if (audioRef.current) audioRef.current.playbackRate = rate;
  }, []);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;
    audio.playbackRate = playbackRate;
  }, [playbackRate, audioSrc]);

  useEffect(() => {
    if (!audioRef.current) return;
    if (!audioSrc || !isPlaying) return;

    audioRef.current
      .play()
      .then(() => setErrorMessage(null))
      .catch(() => {
        setIsPlaying(false);
        setErrorMessage("브라우저에서 오디오 재생을 시작하지 못했습니다.");
      });
  }, [audioSrc, isPlaying]);

  const contextValue = useMemo<PodcastPlayerContextValue>(
    () => ({
      canPlayAudio,
      close,
      closeSheet: () => setIsExpanded(false),
      currentTime,
      duration,
      errorMessage,
      expand: () => setIsExpanded(true),
      goNext,
      goPrevious,
      isBuffering,
      isExpanded,
      isLoadingDetail,
      isPlaying,
      playbackRate,
      playEpisode,
      queue,
      seekBy,
      seekTo,
      selectedEpisode,
      setPlaybackRate,
      togglePlayback,
    }),
    [
      canPlayAudio,
      close,
      currentTime,
      duration,
      errorMessage,
      goNext,
      goPrevious,
      isBuffering,
      isExpanded,
      isLoadingDetail,
      isPlaying,
      playbackRate,
      playEpisode,
      queue,
      seekBy,
      seekTo,
      selectedEpisode,
      setPlaybackRate,
      togglePlayback,
    ],
  );

  return (
    <PodcastPlayerContext.Provider value={contextValue}>
      {children}
      {audioSrc ? (
        <audio
          ref={audioRef}
          src={audioSrc}
          preload="metadata"
          onCanPlay={() => setIsBuffering(false)}
          onDurationChange={(event) => {
            const nextDuration = event.currentTarget.duration;
            if (Number.isFinite(nextDuration)) setDuration(nextDuration);
          }}
          onEnded={() => {
            setIsPlaying(false);
            if (selectedEpisode) {
              void recordPodcastEvent("podcast_complete", selectedEpisode, {
                duration,
              });
            }
            void goNext();
          }}
          onError={() => {
            setIsPlaying(false);
            setIsBuffering(false);
            setErrorMessage("오디오 파일을 불러오지 못했습니다.");
          }}
          onLoadStart={() => setIsBuffering(true)}
          onPause={() => setIsPlaying(false)}
          onPlay={() => setIsPlaying(true)}
          onTimeUpdate={(event) => {
            const nextTime = event.currentTarget.currentTime;
            setCurrentTime(nextTime);
            if (!selectedEpisode || !duration) return;
            const bucket = Math.floor((nextTime / duration) * 4);
            if (bucket > lastProgressBucketRef.current && bucket > 0) {
              lastProgressBucketRef.current = bucket;
              void recordPodcastEvent("podcast_progress", selectedEpisode, {
                completionRate: Math.min(1, nextTime / duration),
                currentTime: nextTime,
              });
            }
          }}
          onWaiting={() => setIsBuffering(true)}
        />
      ) : null}
      {!shouldHidePlayer ? (
        <>
          <PodcastMiniPlayer />
          <PodcastPlayerSheet />
        </>
      ) : null}
    </PodcastPlayerContext.Provider>
  );
}

export function usePodcastPlayer() {
  const context = useContext(PodcastPlayerContext);
  if (!context) {
    throw new Error("usePodcastPlayer must be used inside PodcastPlayerProvider.");
  }
  return context;
}
