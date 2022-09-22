# Bindings that run master make targets inside docker
# Use to avoid installing dependencies on host system

DOCKER_IMAGE_NAME = pysquril

.PHONY: build_docker
build_docker:
	docker build -t $(DOCKER_IMAGE_NAME) - < Dockerfile

.PHONY: docker_test
docker_test: build_docker
	docker run --rm -ti -v $(BASEDIR):/pysquril --workdir /pysquril $(DOCKER_IMAGE_NAME) $(MAKE) test
