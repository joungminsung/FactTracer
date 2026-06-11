"use client";

import { useState } from "react";
import {
  ChevronDown,
  Pause,
  Play,
  RotateCcw,
  RotateCw,
  SkipBack,
  SkipForward,
  X,
} from "lucide-react";
import {
  formatPodcastDuration,
  formatPodcastFormat,
  formatPodcastTime,
  ttsStatusLabel,
} from "@/components/podcast/podcast-display";
import { usePodcastPlayer } from "@/components/podcast/podcast-player-provider";
import { PodcastQueue } from "@/components/podcast/podcast-queue";
import { PodcastSources } from "@/components/podcast/podcast-sources";
import { PodcastTranscript } from "@/components/podcast/podcast-transcript";

type PlayerTab = "transcript" | "queue" | "sources";

const playerTabs: Array<{ id: PlayerTab; label: string }> = [
  { id: "transcript", label: "대사" },
  { id: "queue", label: "다음 재생" },
  { id: "sources", label: "출처" },
];

const playbackRates = [0.8, 1, 1.2, 1.5, 2];

export function PodcastPlayerSheet() {
  const {
    canPlayAudio,
    close,
    closeSheet,
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
    queue,
    seekBy,
    seekTo,
    selectedEpisode,
    setPlaybackRate,
    togglePlayback,
  } = usePodcastPlayer();
  const [activeTab, setActiveTab] = useState<PlayerTab>("transcript");

  if (!selectedEpisode || !isExpanded) return null;

  const progress = duration ? Math.min(100, (currentTime / duration) * 100) : 0;

  return (
    <div className="fixed inset-0 z-[60] bg-white text-gray-950">
      <div className="flex h-full min-h-0 flex-col">
        <header className="border-b border-gray-200">
          <div className="mx-auto flex h-16 max-w-[1520px] items-center justify-between gap-3 px-4 sm:px-7 lg:px-9">
            <button
              type="button"
              onClick={closeSheet}
              className="inline-flex h-10 items-center gap-2 rounded-md border border-gray-200 px-3 text-sm font-bold text-gray-700 hover:bg-gray-50"
            >
              <ChevronDown className="size-5" aria-hidden="true" />
              내리기
            </button>
            <div className="min-w-0 text-center">
              <p className="truncate text-xs font-extrabold text-blue-700">
                FactTracer Podcast
              </p>
              <p className="truncate text-sm font-bold text-gray-500">
                {selectedEpisode.category} · {formatPodcastFormat(selectedEpisode.format)}
              </p>
            </div>
            <button
              type="button"
              onClick={close}
              className="grid size-10 place-items-center rounded-md border border-gray-200 text-gray-700 hover:bg-gray-50"
              aria-label="팟캐스트 닫기"
            >
              <X className="size-5" aria-hidden="true" />
            </button>
          </div>
        </header>

        <main className="min-h-0 flex-1 overflow-y-auto">
          <div className="mx-auto grid max-w-[1520px] gap-8 px-4 py-6 sm:px-7 lg:grid-cols-[minmax(0,0.92fr)_minmax(360px,0.5fr)] lg:px-9 lg:py-9">
            <section className="min-w-0">
              <div className="border-b border-gray-200 pb-6">
                <div className="flex flex-wrap items-center gap-2 text-xs font-extrabold text-gray-500">
                  <span>{selectedEpisode.category}</span>
                  <span aria-hidden="true">·</span>
                  <span>{formatPodcastDuration(selectedEpisode.durationSeconds)}</span>
                  <span aria-hidden="true">·</span>
                  <span>{ttsStatusLabel(selectedEpisode.ttsStatus)}</span>
                </div>
                <h1 className="mt-3 max-w-4xl text-[30px] font-extrabold leading-tight tracking-[-0.02em] text-gray-950 sm:text-[42px]">
                  {selectedEpisode.title}
                </h1>
                <p className="mt-4 max-w-3xl text-[15px] leading-7 text-gray-600">
                  {selectedEpisode.summary || selectedEpisode.subtitle}
                </p>
              </div>

              <div className="border-b border-gray-200 py-6">
                <div className="flex flex-wrap items-center gap-3">
                  {selectedEpisode.hosts.length > 0 ? (
                    selectedEpisode.hosts.map((host) => (
                      <div
                        key={host.id}
                        className="flex min-h-14 items-center gap-3 rounded-md border border-gray-200 px-3"
                      >
                        <span className="grid size-9 place-items-center rounded-full bg-blue-50 text-sm font-extrabold text-blue-700">
                          {host.name.slice(0, 1)}
                        </span>
                        <span className="min-w-0">
                          <span className="block text-sm font-extrabold text-gray-950">
                            {host.name}
                          </span>
                          <span className="block text-xs font-semibold text-gray-500">
                            {host.role} · {host.tone}
                          </span>
                        </span>
                      </div>
                    ))
                  ) : (
                    <div className="rounded-md border border-gray-200 px-3 py-3 text-sm font-semibold text-gray-500">
                      진행 캐릭터 정보를 불러오는 중입니다.
                    </div>
                  )}
                </div>
              </div>

              <div className="py-6">
                <div className="flex items-center justify-center gap-2">
                  <button
                    type="button"
                    onClick={goPrevious}
                    className="grid size-11 place-items-center rounded-md border border-gray-200 text-gray-700 hover:bg-gray-50"
                    aria-label="이전 팟캐스트"
                  >
                    <SkipBack className="size-5" aria-hidden="true" />
                  </button>
                  <button
                    type="button"
                    onClick={() => seekBy(-15)}
                    className="grid size-11 place-items-center rounded-md border border-gray-200 text-gray-700 hover:bg-gray-50"
                    aria-label="15초 뒤로"
                  >
                    <RotateCcw className="size-5" aria-hidden="true" />
                  </button>
                  <button
                    type="button"
                    onClick={() => void togglePlayback()}
                    disabled={isLoadingDetail}
                    className="grid size-14 place-items-center rounded-full bg-gray-950 text-white disabled:cursor-not-allowed disabled:opacity-50"
                    aria-label={isPlaying ? "팟캐스트 일시정지" : "팟캐스트 재생"}
                  >
                    {isPlaying ? (
                      <Pause className="size-6" aria-hidden="true" />
                    ) : (
                      <Play className="ml-0.5 size-6" aria-hidden="true" />
                    )}
                  </button>
                  <button
                    type="button"
                    onClick={() => seekBy(15)}
                    className="grid size-11 place-items-center rounded-md border border-gray-200 text-gray-700 hover:bg-gray-50"
                    aria-label="15초 앞으로"
                  >
                    <RotateCw className="size-5" aria-hidden="true" />
                  </button>
                  <button
                    type="button"
                    onClick={() => void goNext()}
                    className="grid size-11 place-items-center rounded-md border border-gray-200 text-gray-700 hover:bg-gray-50"
                    aria-label="다음 팟캐스트"
                  >
                    <SkipForward className="size-5" aria-hidden="true" />
                  </button>
                </div>

                <div className="mt-5">
                  <input
                    type="range"
                    min="0"
                    max={Math.max(1, duration)}
                    value={Math.min(currentTime, Math.max(1, duration))}
                    onChange={(event) => seekTo(Number(event.target.value))}
                    className="h-2 w-full accent-blue-600"
                    aria-label="재생 위치"
                    disabled={!canPlayAudio}
                  />
                  <div className="mt-2 flex items-center justify-between text-xs font-bold text-gray-500">
                    <span>{formatPodcastTime(currentTime)}</span>
                    <span>{formatPodcastTime(duration)}</span>
                  </div>
                  {!canPlayAudio ? (
                    <p className="mt-2 text-sm font-bold text-amber-600">
                      {ttsStatusLabel(selectedEpisode.ttsStatus)}
                    </p>
                  ) : null}
                  {isBuffering ? (
                    <p className="mt-2 text-sm font-bold text-blue-700">
                      오디오를 불러오고 있습니다.
                    </p>
                  ) : null}
                  {errorMessage ? (
                    <p className="mt-2 text-sm font-bold text-red-600">
                      {errorMessage}
                    </p>
                  ) : null}
                </div>

                <div className="mt-5 flex flex-wrap items-center gap-2">
                  {playbackRates.map((rate) => (
                    <button
                      type="button"
                      key={rate}
                      onClick={() => setPlaybackRate(rate)}
                      className={`h-9 rounded-md border px-3 text-xs font-bold ${
                        playbackRate === rate
                          ? "border-blue-600 bg-blue-50 text-blue-700"
                          : "border-gray-200 text-gray-600 hover:bg-gray-50"
                      }`}
                    >
                      {rate}x
                    </button>
                  ))}
                  <span className="ml-auto text-xs font-bold text-gray-500">
                    진행률 {Math.round(progress)}%
                  </span>
                </div>
              </div>
            </section>

            <aside className="min-w-0">
              <div className="sticky top-5">
                <div className="grid grid-cols-3 border-b border-gray-200">
                  {playerTabs.map((tab) => (
                    <button
                      type="button"
                      key={tab.id}
                      onClick={() => setActiveTab(tab.id)}
                      className={`h-11 border-b-2 text-sm font-extrabold ${
                        activeTab === tab.id
                          ? "border-blue-600 text-blue-700"
                          : "border-transparent text-gray-500 hover:text-gray-950"
                      }`}
                    >
                      {tab.label}
                    </button>
                  ))}
                </div>

                <div className="mt-4">
                  {activeTab === "transcript" ? (
                    <PodcastTranscript
                      currentTime={currentTime}
                      episode={selectedEpisode}
                    />
                  ) : null}
                  {activeTab === "queue" ? <PodcastQueue queue={queue} /> : null}
                  {activeTab === "sources" ? (
                    <PodcastSources episode={selectedEpisode} />
                  ) : null}
                </div>
              </div>
            </aside>
          </div>
        </main>
      </div>
    </div>
  );
}
