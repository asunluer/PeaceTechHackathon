<svelte:head>
  <title>SAFE-ARCHIVE</title>
  <meta name="description" content="Structured preservation of publicly observable online abuse evidence." />
</svelte:head>

<div class="min-h-screen bg-slate-50 text-slate-900">
  <header class="border-b border-slate-200 bg-white">
    <div class="mx-auto flex max-w-5xl items-center justify-between px-6 py-5">
      <div class="flex items-center gap-3">
        <span class="flex size-9 items-center justify-center rounded-lg bg-slate-900 text-sm font-bold text-white" aria-hidden="true">SA</span>
        <span class="text-sm font-semibold tracking-[0.18em]">SAFE-ARCHIVE</span>
      </div>
      <a href="/login" class="rounded-md border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-700">Sign in</a>
    </div>
  </header>

  <main class="mx-auto max-w-5xl px-6 py-20 sm:py-28">
    <div class="max-w-2xl">
      <p class="mb-5 text-sm font-semibold uppercase tracking-[0.2em] text-slate-600">For survivor support organizations</p>
      <h1 class="text-4xl font-semibold tracking-tight sm:text-5xl">Preserve what is publicly visible before it disappears.</h1>
      <p class="mt-6 text-lg leading-8 text-slate-600">SAFE-ARCHIVE is being built to help NGOs organize submitted links, preserve public page captures, and review evidence with clear provenance.</p>
      <div class="mt-10 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 class="text-base font-semibold">Preservation principles</h2>
        <ul class="mt-4 space-y-3 text-sm leading-6 text-slate-600">
          <li>Capture only publicly observable information from a submitted URL.</li>
          <li>Keep original evidence separate from investigator notes and AI assistance.</li>
          <li>Record capture details and integrity hashes without claiming legal certification.</li>
        </ul>
      </div>
    </div>
  </main>
</div>
