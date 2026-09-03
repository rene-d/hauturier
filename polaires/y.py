#!/usr/bin/env python3

from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfparser import PDFParser
from pdfminer.pdftypes import PDFStream


fname = "Polar_curves_-_Sun_Odyssey_419_-_Std_keel_-_140%_Genoa_+_Code_0.pdf"
fp = open(fname, "rb")
parser = PDFParser(fp)
doc = PDFDocument(parser, None)

objids = (objid for xref in doc.xrefs for objid in xref.get_objids())

for objid in sorted(objids):
    obj = doc.getobj(objid)
    if isinstance(obj, PDFStream):

        # uniquement {'Filter': /'FlateDecode', 'Length': XXX}
        if len(obj.attrs)!=2:continue

        # print(objid, type(obj))
        data = obj.get_data()
        print(objid, type(obj), obj.get_filters(), obj.attrs)
        # print(data)
