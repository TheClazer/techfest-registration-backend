# Convenience targets. Assumes an activated virtualenv (see README for setup).
.PHONY: install run test volunteer docker docker-run

install:
	pip install -r requirements.txt

run:
	uvicorn app.main:app --reload

test:
	pytest

volunteer:
	python -m scripts.create_volunteer --email volunteer@rvce.edu --password password123 --name "Gate Volunteer"

docker:
	docker build -t techfest .

docker-run:
	docker run -p 8000:8000 --env-file .env techfest
