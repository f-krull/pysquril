BASEDIR:=$(shell dirname $(realpath $(firstword $(MAKEFILE_LIST))))

include make_docker.mk

all: text

.PHONY: test
test: venv
	. env/bin/activate; python -m pip install -r requirements.txt
	# -i           -> pass to initdb
	# --auth=trusv -> trust all(!) local users
	pg_virtualenv -i --auth=trust bash -c "\
		createuser pysquril_user; \
		createdb -O pysquril_user pysquril_db; \
		. env/bin/activate; \
		python -m pytest -vv pysquril/tests.py \
	"

.PHONY: venv
venv: env/bin/activate
	. env/bin/activate

env/bin/activate:
	python3 -m venv env

# notes:
# sudo apt install python3.10-venv
# python -m pip install psycopg2-binary
# python -m pip freeze > requirements.txt
