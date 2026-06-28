# Convenience targets. Assumes an activated virtualenv (see README for setup).
.PHONY: install run run-prod test volunteer docker docker-run

install:
	pip install -r requirements.txt

run:
	uvicorn app.main:app --reload

# Production-style run with the load-shedding valve (see SCALE.md): Uvicorn
# returns 503 beyond --limit-concurrency simultaneous connections.
run-prod:
	uvicorn app.main:app --host 0.0.0.0 --port 8000 --limit-concurrency 200

test:
	pytest

volunteer:
	python -m scripts.create_volunteer --email volunteer@rvce.edu --password password123 --name "Gate Volunteer"

docker:
	docker build -t techfest .

docker-run:
	docker run -p 8000:8000 --env-file .env techfest
