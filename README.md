# NBA Historical Comparison

A local-first NBA historical-comparison application. The FastAPI backend discovers the actual schema in the Wyatt Walsh Kaggle `nba.sqlite` file at runtime, normalizes compatible player and team season data, and returns statistically comparable historical matches. The Next.js frontend presents those matches through an accessible, animated comparison dashboard.

## Status

The repository has been scaffolded without the dataset. Place `nba.sqlite` at the project root before starting the backend; the health endpoint will identify whether the dataset can be normalized and list the discovered tables.

## Development

Backend and frontend setup commands will be documented as the first working slices land. The project intentionally never downloads, embeds, or commits the Kaggle database.
