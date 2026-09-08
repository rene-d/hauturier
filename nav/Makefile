CONFIG ?= config.yaml
OUT    ?= build/nav.pdf

default: pdf

pdf:
	./nav.py -c $(CONFIG) -o $(OUT)

open:
	./nav.py -c $(CONFIG) -o $(OUT) --open

# ignore le cache HTTP (les pages mensuelles sont figées, sauf correction du site)
refresh:
	./nav.py -c $(CONFIG) -o $(OUT) --no-cache

# compare les créneaux de porte calculés au calendrier officiel du port
verif:
	./verif_porte_trebeurden.py

clean:
	rm -rf build

distclean: clean
	rm -rf cache

.PHONY: default pdf open refresh verif clean distclean
