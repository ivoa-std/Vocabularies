all: clean vocabs.conf
	python convert.py ALL

dist.tar.gz: all
	tar --transform='s/^build\///' -czf $@ build

FAIL = $(error "Need to define ROOT_URI for make local")

local: clean
# ROOT_URI at ARI: http://docs.g-vo.org/rdf
ifdef ROOT_URI
	python convert.py --root-uri $(ROOT_URI) vocabs.conf
	(cd build; tar -czf ../local.tar.gz *)
else
	$(FAIL)
endif

clean:
	rm -rf build
