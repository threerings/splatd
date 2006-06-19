# Based on the DarwinPorts' Guide build system,
# Originally contributed by Will Barton and Michael Maibaum.

## Targets
#
# xhtml : Makes unformated, chunked xhtml from xml
# tidy  : Tidies (formats, indents) xhtml
# clean : Deletes xhtml
# all   : xhtml

## Details and Caveats
# To use local dtd catalogs you must first create the catalog, I currently
# assume the catalogs are in ${PREFIX}/etc/xml, if yours are elswhere you
# should alter the $XML_CATALOG_FILES variable. 

# set XML_DEBUG_CATALOG= to see catalog debugging info

SOURCEDIR?=		xml
DOCBOOK_XSL?=	        ${PREFIX}/share/xsl/docbook-xsl/
XHTMLDIR?=		xhtml
STYLESHEET?=	        ${DOCBOOK_XSL}/html/chunk.xsl
XSTYLESHEET?=	        ${DOCBOOK_XSL}/xhtml/chunk.xsl
XML_CATALOG_FILES?=	${PREFIX}/etc/xml/catalog
XML_DEBUG_CATALOG?=
CSS_STYLESHEET?=	docbook.css
RESOURCES?=		resources/
USERLEVEL?=		user
STRINGPARAMS?=		--stringparam html.stylesheet ${CSS_STYLESHEET}

.PHONY: all
.PHONY: clean
#.PHONY: install
.PHONY: xhtml
.PHONY: check
.PHONY: tidy

xhtml:
	mkdir -p ${XHTMLDIR}
	install ${RESOURCES}${CSS_STYLESHEET} ${XHTMLDIR}
	xsltproc --nonet --xinclude ${STRINGPARAMS} -o "${XHTMLDIR}/" "${XSTYLESHEET}" "${SOURCEDIR}/splat.xml"

check:
	xmllint --xinclude --noout "${SOURCEDIR}/splat.xml"

# XXX tidy breaks the xhtml and html
tidy:
# This target will *only* work if you have installed the www/tidy port
# or if have tidy from http://tidy.sourceforge.net/ installed somewhere
# in your path.
	-tidy -quiet -modify -indent -xml ${XHTMLDIR}/*

clean:
	rm -fr ${HTMLDIR} ${XHTMLDIR}
