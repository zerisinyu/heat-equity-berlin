.PHONY: all fetch pipeline serve clean

all: pipeline

pipeline:
	uv run python run.py

fetch:
	uv run python run.py fetch

serve:
	cd web && python3 -m http.server 8000

clean:
	rm -rf data/processed/*
