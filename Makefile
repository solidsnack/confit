.PHONY: pep8
pep8:
	pep8 confit | tee pep8.txt | head -n8

.PHONY: install
install:
	python setup.py install

.PHONY: clean
clean:
	find . -type f -name '*'.pyc -delete
