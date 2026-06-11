"use client";

import { FormEvent, KeyboardEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { Search } from "lucide-react";

export function HeaderSearchForm() {
  const router = useRouter();
  const [query, setQuery] = useState("");

  function navigateToSearch() {
    const params = new URLSearchParams();

    if (query.trim()) {
      params.set("q", query.trim());
    }

    router.push(params.size ? `/?${params.toString()}` : "/");
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    navigateToSearch();
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key !== "Enter") return;
    event.preventDefault();
    navigateToSearch();
  }

  return (
    <form
      role="search"
      onSubmit={handleSubmit}
      className="hidden h-9 w-[250px] min-w-0 items-center gap-2 rounded-sm border border-gray-300 bg-white px-3 text-gray-500 focus-within:border-gray-700 md:flex"
    >
      <input
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        onKeyDown={handleKeyDown}
        className="w-full min-w-0 bg-transparent text-sm text-gray-900 outline-none placeholder:text-gray-400"
        placeholder="사건, 키워드 검색"
        aria-label="사건, 키워드 검색"
        type="search"
      />
      <button
        type="submit"
        aria-label="검색"
        className="-mr-1 inline-flex size-7 items-center justify-center rounded-sm text-gray-500 hover:bg-gray-100 hover:text-gray-900"
      >
        <Search className="size-4" aria-hidden="true" />
      </button>
    </form>
  );
}
