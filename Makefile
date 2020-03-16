LOCAL_WEB_ROOT?=/var/www/htdocs/rdf

all: clean vocabs.conf
	python3 convert.py ALL

dist.tar.gz: all
	tar --transform='s/^build\///' -czf $@ build

FAIL = $(error "Need to define ROOT_URI for make local")

local: clean
	python3 convert.py --root-uri http://localhost/rdf \
		--dest-dir $(LOCAL_WEB_ROOT) ALL

clean:
	rm -rf build
