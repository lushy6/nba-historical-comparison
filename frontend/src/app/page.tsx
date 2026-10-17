import { SearchExperience } from "@/components/search-experience";


export default function HomePage() {
  return <>
    {process.env.NEXT_PUBLIC_DEMO_DATA === "true" && (
      <aside aria-label="Demo data notice" style={{ padding: "12px 24px", textAlign: "center", background: "#f4e8c5", color: "#332a19" }}>
        Fictional demo catalog — player names, teams, and statistics are synthetic. Scores illustrate the comparison method only.
      </aside>
    )}
    <SearchExperience />
  </>;
}
