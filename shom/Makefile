default: nav.pdf

.SUFFIXES: .pdf

.tex.pdf:
	rm -f $@
	texfot lualatex -output-format=pdf -interaction=nonstopmode $<
	test -f $@
	open $@

nav.tex nav2.tex: nav.py tides.py spm.py hdm.py sun_ephem.py
	./nav.py

clean:
	-rm -f *.log *.aux *.log *.tex *.pdf *.out