#!/usr/bin/env python3


import traceback
import sys
 
from eccodes import *
 
import eccodes

with eccodes.FileReader("CMEMS-SW.20231004.2330.grb2") as reader:

    message = next(reader)

    print(list(message.values()))

#     for k in sorted(message.keys()):
#         print(f"{k:<40} {message.get(k)}")



# 
INPUT = '../../data/tp_ecmwf.grib'
OUTPUT = 'out.grb2'
VERBOSE = 1  # verbose error reporting
 
 
def example():
    sample_id = codes_grib_new_from_samples("regular_ll_sfc_grib2")
    fout = open(OUTPUT, 'wb')
 
    keys = {
        'dataDate': 20080104,
        'startStep': 0,
        'endStep': 15,
        'stepType': 'instant',
        'table2Version': 2,
        'indicatorOfParameter': 61,
        'decimalPrecision': 2,
    }
 
 
            # keys['startStep'] += 12
            # keys['endStep'] += 12

    clone_id = codes_clone(sample_id)

    for key in keys:
        codes_set(clone_id, key, keys[key])

    result= [0.0, 0.2, 0.2, 0.1, 0.5, 0.7]

    codes_set_values(clone_id, result )

    codes_write(clone_id, fout)

 
    fout.close()
 
 
def main():
    try:
        example()
    except CodesInternalError as err:
        if VERBOSE:
            traceback.print_exc(file=sys.stderr)
        else:
            sys.stderr.write(err.msg + '\n')
 
        return 1
 
 
if __name__ == "__main__":
    sys.exit(main())

