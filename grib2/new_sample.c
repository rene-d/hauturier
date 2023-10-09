/*
 * (C) Copyright 2005- ECMWF.
 *
 * This software is licensed under the terms of the Apache Licence Version 2.0
 * which can be obtained at http://www.apache.org/licenses/LICENSE-2.0.
 *
 * In applying this licence, ECMWF does not waive the privileges and immunities granted to it by
 * virtue of its status as an intergovernmental organisation nor does it submit to any jurisdiction.
 */

#include <eccodes.h>

#define iDirectionIncrement 10000
#define jDirectionIncrement 10000

#define Ni 128      // nombre de points en abscisse, i.e. en longitudes  
#define Nj 32       // nombre de points en ordonnée, i.e. en latitudes

/* This code was generated automatically */

int main(int argc, char** argv)
{
    codes_handle* h    = NULL;
    size_t size        = 0;
    double* vdouble    = NULL;
    FILE* f            = NULL;
    const void* buffer = NULL;

    if (argc != 2) {
        fprintf(stderr, "usage: %s out\n", argv[0]);
        exit(1);
    }

    /* h = codes_grib_handle_new_from_samples(NULL, "GRIB2"); */
    h = codes_handle_new_from_samples(NULL, "GRIB2");
    if (!h) {
        fprintf(stderr, "Cannot create grib handle\n");
        return 1;
    }

    CODES_CHECK(codes_set_long(h, "parametersVersion", 1), 0);
    CODES_CHECK(codes_set_long(h, "truncateLaplacian", 0), 0);
    CODES_CHECK(codes_set_long(h, "truncateDegrees", 0), 0);
    CODES_CHECK(codes_set_long(h, "dummy", 1), 0);
    CODES_CHECK(codes_set_long(h, "changingPrecision", 0), 0);
    CODES_CHECK(codes_set_long(h, "unitsFactor", 1), 0);
    CODES_CHECK(codes_set_long(h, "unitsBias", 0), 0);
    CODES_CHECK(codes_set_long(h, "timeRangeIndicatorFromStepRange", -1), 0);
    CODES_CHECK(codes_set_long(h, "missingValue", 9999), 0);

    /* 0 = Meteorological products (grib2/tables/4/0.0.table)  */
    CODES_CHECK(codes_set_long(h, "discipline", 0), 0);

    CODES_CHECK(codes_set_long(h, "editionNumber", 2), 0);

    /* 98 = European Center for Medium-Range Weather Forecasts */
    CODES_CHECK(codes_set_long(h, "centre", 98), 0);

    CODES_CHECK(codes_set_long(h, "subCentre", 0), 0);

    /* 4 = Version implemented on 7 November 2007 (grib2/tables/1.0.table)  */
    CODES_CHECK(codes_set_long(h, "tablesVersion", 4), 0);


    /* 0 = Local tables not used  (grib2/tables/4/1.1.table)  */
    CODES_CHECK(codes_set_long(h, "localTablesVersion", 0), 0);


    /* 1 = Start of forecast (grib2/tables/4/1.2.table)  */
    CODES_CHECK(codes_set_long(h, "significanceOfReferenceTime", 1), 0);

    CODES_CHECK(codes_set_long(h, "year", 2007), 0);
    CODES_CHECK(codes_set_long(h, "month", 3), 0);
    CODES_CHECK(codes_set_long(h, "day", 23), 0);
    CODES_CHECK(codes_set_long(h, "hour", 12), 0);
    CODES_CHECK(codes_set_long(h, "minute", 0), 0);
    CODES_CHECK(codes_set_long(h, "second", 0), 0);
    CODES_CHECK(codes_set_long(h, "dataDate", 20070323), 0);
    CODES_CHECK(codes_set_long(h, "dataTime", 1200), 0);

    /* 0 = Operational products (grib2/tables/4/1.3.table)  */
    CODES_CHECK(codes_set_long(h, "productionStatusOfProcessedData", 0), 0);

    /* 2 = Analysis and forecast products (grib2/tables/4/1.4.table)  */
    CODES_CHECK(codes_set_long(h, "typeOfProcessedData", 2), 0);

    CODES_CHECK(codes_set_long(h, "selectStepTemplateInterval", 1), 0);
    CODES_CHECK(codes_set_long(h, "selectStepTemplateInstant", 1), 0);
    CODES_CHECK(codes_set_long(h, "grib2LocalSectionPresent", 0), 0);

    /* 0 = Specified in Code table 3.1 (grib2/tables/4/3.0.table)  */
    CODES_CHECK(codes_set_long(h, "sourceOfGridDefinition", 0), 0);

    CODES_CHECK(codes_set_long(h, "numberOfDataPoints", Ni*Nj), 0);
    CODES_CHECK(codes_set_long(h, "numberOfOctectsForNumberOfPoints", 0), 0);

    /* 0 = There is no appended list (grib2/tables/4/3.11.table)  */
    CODES_CHECK(codes_set_long(h, "interpretationOfNumberOfPoints", 0), 0);

    CODES_CHECK(codes_set_long(h, "PLPresent", 0), 0);

    /* 0 = Latitude/longitude. Also called equidistant cylindrical, or Plate Carree (grib2/tables/4/3.1.table)  */
    CODES_CHECK(codes_set_long(h, "gridDefinitionTemplateNumber", 0), 0);


    /* 0 = Earth assumed spherical with radius = 6,367,470.0 m (grib2/tables/4/3.2.table)  */
    CODES_CHECK(codes_set_long(h, "shapeOfTheEarth", 0), 0);

    CODES_CHECK(codes_set_missing(h, "scaleFactorOfRadiusOfSphericalEarth"), 0);
    CODES_CHECK(codes_set_missing(h, "scaledValueOfRadiusOfSphericalEarth"), 0);
    CODES_CHECK(codes_set_missing(h, "scaleFactorOfEarthMajorAxis"), 0);
    CODES_CHECK(codes_set_missing(h, "scaledValueOfEarthMajorAxis"), 0);
    CODES_CHECK(codes_set_missing(h, "scaleFactorOfEarthMinorAxis"), 0);
    CODES_CHECK(codes_set_missing(h, "scaledValueOfEarthMinorAxis"), 0);
    CODES_CHECK(codes_set_long(h, "radius", 6367470), 0);
    CODES_CHECK(codes_set_long(h, "Ni", Ni), 0);
    CODES_CHECK(codes_set_long(h, "Nj", Nj), 0);
    CODES_CHECK(codes_set_long(h, "basicAngleOfTheInitialProductionDomain", 0), 0);
    CODES_CHECK(codes_set_long(h, "mBasicAngle", 0), 0);
    CODES_CHECK(codes_set_long(h, "angleMultiplier", 1), 0);
    CODES_CHECK(codes_set_long(h, "mAngleMultiplier", 1000000), 0);
    CODES_CHECK(codes_set_missing(h, "subdivisionsOfBasicAngle"), 0);
    CODES_CHECK(codes_set_long(h, "angleDivisor", 1000000), 0);
    CODES_CHECK(codes_set_long(h, "latitudeOfFirstGridPoint", 48000000), 0);
    CODES_CHECK(codes_set_long(h, "longitudeOfFirstGridPoint", 356000000), 0);

    /* 48 = 00110000
    (3=1)  i direction increments given
    (4=1)  j direction increments given
    (5=0)  Resolved u- and v- components of vector quantities relative to easterly and northerly directions
    See grib2/tables/[tablesVersion]/3.3.table */
    CODES_CHECK(codes_set_long(h, "resolutionAndComponentFlags", 48), 0);

    CODES_CHECK(codes_set_long(h, "iDirectionIncrementGiven", 1), 0);
    CODES_CHECK(codes_set_long(h, "jDirectionIncrementGiven", 1), 0);
    CODES_CHECK(codes_set_long(h, "uvRelativeToGrid", 0), 0);
    CODES_CHECK(codes_set_long(h, "latitudeOfLastGridPoint", 48000000-Nj*jDirectionIncrement), 0);
    CODES_CHECK(codes_set_long(h, "longitudeOfLastGridPoint", 356000000+Ni*iDirectionIncrement), 0);
    CODES_CHECK(codes_set_long(h, "iDirectionIncrement", iDirectionIncrement), 0);
    CODES_CHECK(codes_set_long(h, "jDirectionIncrement", jDirectionIncrement), 0);

    /* 0 = 00000000
    (1=0)  Points of first row or column scan in the +i (+x) direction
    (2=0)  Points of first row or column scan in the -j (-y) direction
    (3=0)  Adjacent points in i (x) direction are consecutive
    (4=0)  All rows scan in the same direction
    See grib2/tables/[tablesVersion]/3.4.table */
    CODES_CHECK(codes_set_long(h, "scanningMode", 0), 0);

    CODES_CHECK(codes_set_long(h, "iScansNegatively", 0), 0);
    CODES_CHECK(codes_set_long(h, "jScansPositively", 0), 0);
    CODES_CHECK(codes_set_long(h, "jPointsAreConsecutive", 0), 0);
    CODES_CHECK(codes_set_long(h, "alternativeRowScanning", 0), 0);
    CODES_CHECK(codes_set_long(h, "iScansPositively", 1), 0);

    /* ITERATOR */


    /* NEAREST */

    CODES_CHECK(codes_set_long(h, "timeRangeIndicator", 0), 0);
    CODES_CHECK(codes_set_long(h, "NV", 0), 0);
    CODES_CHECK(codes_set_long(h, "neitherPresent", 0), 0);

    /* 0 = Analysis or forecast at a horizontal level or in a horizontal layer at a point in time (grib2/tables/4/4.0.table)  */
    CODES_CHECK(codes_set_long(h, "productDefinitionTemplateNumber", 0), 0);


    /* Parameter information */


    /* 0 = Temperature (grib2/tables/4/4.1.0.table)  */
    CODES_CHECK(codes_set_long(h, "parameterCategory", 0), 0);


    /* 0 = Temperature  (K)  (grib2/tables/4/4.2.0.0.table)  */
    CODES_CHECK(codes_set_long(h, "parameterNumber", 0), 0);


    /* 0 = Analysis (grib2/tables/4/4.3.table)  */
    CODES_CHECK(codes_set_long(h, "typeOfGeneratingProcess", 0), 0);

    CODES_CHECK(codes_set_long(h, "backgroundProcess", 255), 0);
    CODES_CHECK(codes_set_long(h, "generatingProcessIdentifier", 128), 0);
    CODES_CHECK(codes_set_long(h, "hoursAfterDataCutoff", 0), 0);
    CODES_CHECK(codes_set_long(h, "minutesAfterDataCutoff", 0), 0);

    /* 1 = Hour (grib2/tables/4/4.4.table)  */
    CODES_CHECK(codes_set_long(h, "indicatorOfUnitOfTimeRange", 1), 0);


    /* 1 = Hour (stepUnits.table)  */
    CODES_CHECK(codes_set_long(h, "stepUnits", 1), 0);

    CODES_CHECK(codes_set_long(h, "forecastTime", 0), 0);

    /* 1 = Ground or water surface  (grib2/tables/4/4.5.table)  */
    CODES_CHECK(codes_set_long(h, "typeOfFirstFixedSurface", 1), 0);

    CODES_CHECK(codes_set_missing(h, "scaleFactorOfFirstFixedSurface"), 0);
    CODES_CHECK(codes_set_missing(h, "scaledValueOfFirstFixedSurface"), 0);

    /* 255 = Missing (grib2/tables/4/4.5.table)  */
    CODES_CHECK(codes_set_long(h, "typeOfSecondFixedSurface", 255), 0);

    CODES_CHECK(codes_set_missing(h, "scaleFactorOfSecondFixedSurface"), 0);
    CODES_CHECK(codes_set_missing(h, "scaledValueOfSecondFixedSurface"), 0);
    CODES_CHECK(codes_set_long(h, "level", 0), 0);
    CODES_CHECK(codes_set_long(h, "bottomLevel", 0), 0);
    CODES_CHECK(codes_set_long(h, "topLevel", 0), 0);
    CODES_CHECK(codes_set_long(h, "dummyc", 0), 0);
    CODES_CHECK(codes_set_long(h, "PVPresent", 0), 0);

    /* grib 2 Section 5 DATA REPRESENTATION SECTION */

    CODES_CHECK(codes_set_long(h, "numberOfValues", Ni*Nj), 0);

    /* 0 = Grid point data - simple packing (grib2/tables/4/5.0.table)  */
    CODES_CHECK(codes_set_long(h, "dataRepresentationTemplateNumber", 0), 0);

    CODES_CHECK(codes_set_long(h, "decimalScaleFactor", 0), 0);
    CODES_CHECK(codes_set_long(h, "bitsPerValue", 0), 0);

    /* 0 = Floating point (grib2/tables/4/5.1.table)  */
    CODES_CHECK(codes_set_long(h, "typeOfOriginalFieldValues", 0), 0);

    CODES_CHECK(codes_set_long(h, "representationMode", 0), 0);

    /* grib 2 Section 6 BIT-MAP SECTION */


    /* 255 = A bit map does not apply to this product (grib2/tables/4/6.0.table)  */
    CODES_CHECK(codes_set_long(h, "bitMapIndicator", 255), 0);

    CODES_CHECK(codes_set_long(h, "bitmapPresent", 0), 0);

    /* grib 2 Section 7 data */

    size    = Ni*Nj;
    vdouble = (double*)calloc(size, sizeof(double));
    if (!vdouble) {
        fprintf(stderr, "failed to allocate %zu bytes\n", size * sizeof(double));
        exit(1);
    }
    for (size_t i =0;i<size;i++) vdouble[i] = (i/Nj)*(i/Ni);


    CODES_CHECK(codes_set_double_array(h, "values", vdouble, size), 0);
    free(vdouble);

    /* Save the message */

    f = fopen(argv[1], "wb");
    if (!f) {
        perror(argv[1]);
        exit(1);
    }

    CODES_CHECK(codes_get_message(h, &buffer, &size), 0);

    if (fwrite(buffer, 1, size, f) != size) {
        perror(argv[1]);
        exit(1);
    }

    if (fclose(f)) {
        perror(argv[1]);
        exit(1);
    }

    codes_handle_delete(h);
    grib_context_delete(grib_context_get_default());
    return 0;
}
