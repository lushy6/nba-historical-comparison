export default function HomePage() {
  return (
    <main className="page-shell">
      <nav aria-label="Primary" className="site-nav">
        <a className="wordmark" href="#search">
          <span aria-hidden="true" className="wordmark-mark">SE</span>
          <span>Season Echoes</span>
        </a>
        <p className="nav-note">NBA historical comparison</p>
      </nav>

      <section className="hero" aria-labelledby="page-title">
        <p className="eyebrow">A different kind of comparison</p>
        <h1 id="page-title">Find the season that echoes today.</h1>
        <p className="hero-copy">
          Search a player or a team. We will trace the statistical shape of their season
          through NBA history—pace, efficiency, volume, and the details in between.
        </p>

        <form id="search" className="search-frame" role="search">
          <label className="sr-only" htmlFor="nba-history-search">Search NBA history</label>
          <svg aria-hidden="true" className="search-icon" viewBox="0 0 24 24">
            <circle cx="11" cy="11" r="6.5" />
            <path d="m16 16 4.25 4.25" />
          </svg>
          <input
            id="nba-history-search"
            className="search-input"
            name="q"
            type="search"
            placeholder="Search players or teams"
            autoComplete="off"
          />
          <span className="search-hint" aria-hidden="true">⌘ K</span>
        </form>

        <p className="search-caption">
          Powered by the local NBA historical database. No scores are guessed.
        </p>
      </section>

      <aside className="method-note" aria-label="Comparison methodology">
        <span className="method-rule" aria-hidden="true" />
        <p>
          <strong>How it works</strong>
          <span>Stat profiles are standardized before we measure the nearest historical shape.</span>
        </p>
      </aside>
    </main>
  );
}
