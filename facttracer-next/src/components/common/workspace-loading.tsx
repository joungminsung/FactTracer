export function WorkspaceLoading({
  context = "이슈 기록",
  title = "내용을 불러오는 중입니다",
}: {
  context?: string;
  title?: string;
}) {
  return (
    <main className="mx-auto max-w-[1440px] px-6 py-8">
      <section className="border-b border-gray-200 pb-7">
        <p className="text-sm font-semibold text-blue-600">{context}</p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight text-gray-900 sm:text-4xl">
          {title}
        </h1>
        <p className="mt-3 max-w-3xl text-base leading-8 text-gray-600">
          사건 기록과 검토 항목을 정리하고 있습니다.
        </p>
      </section>

      <section className="grid gap-8 py-8 lg:grid-cols-[260px_minmax(0,1fr)_320px]">
        <aside className="border-b border-gray-200 pb-6 lg:border-r lg:border-b-0 lg:pr-5">
          <div className="h-5 w-24 rounded-sm bg-gray-100" />
          <div className="mt-5 divide-y divide-gray-100 border-t border-gray-200">
            {[1, 2, 3].map((item) => (
              <div key={item} className="py-4">
                <div className="h-4 w-3/4 rounded-sm bg-gray-100" />
                <div className="mt-2 h-3 w-1/2 rounded-sm bg-gray-100" />
              </div>
            ))}
          </div>
        </aside>

        <article className="min-w-0">
          <div className="border-b border-gray-200 pb-7">
            <div className="h-5 w-32 rounded-sm bg-gray-100" />
            <div className="mt-4 h-8 w-3/4 rounded-sm bg-gray-100" />
            <div className="mt-4 h-4 w-full max-w-2xl rounded-sm bg-gray-100" />
            <div className="mt-2 h-4 w-5/6 max-w-2xl rounded-sm bg-gray-100" />
          </div>
          <div className="divide-y divide-gray-100 border-t border-gray-200">
            {[1, 2, 3, 4].map((item) => (
              <div
                key={item}
                className="grid gap-4 py-5 md:grid-cols-[120px_minmax(0,1fr)_120px]"
              >
                <div className="h-4 rounded-sm bg-gray-100" />
                <div>
                  <div className="h-4 rounded-sm bg-gray-100" />
                  <div className="mt-2 h-3 w-2/3 rounded-sm bg-gray-100" />
                </div>
                <div className="h-6 rounded-sm bg-gray-100" />
              </div>
            ))}
          </div>
        </article>

        <aside className="border-t border-gray-200 pt-6 lg:border-t-0 lg:border-l lg:pl-6 lg:pt-0">
          <div className="h-5 w-24 rounded-sm bg-gray-100" />
          <div className="mt-5 divide-y divide-gray-100 border-t border-gray-200">
            {[1, 2, 3].map((item) => (
              <div key={item} className="py-4">
                <div className="h-4 rounded-sm bg-gray-100" />
              </div>
            ))}
          </div>
        </aside>
      </section>
    </main>
  );
}
