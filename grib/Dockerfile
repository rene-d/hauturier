FROM alpine:latest AS builder

RUN apk add --no-cache gcc musl-dev gfortran make

ENV CC gcc
ENV FC gfortran

RUN wget -q ftp://ftp.cpc.ncep.noaa.gov/wd51we/wgrib2/wgrib2.tgz

RUN tar xzf wgrib2.tgz && \
    cd grib2 && \
    make -j4 USE_JASPER=0 USE_NETCDF3=0

FROM alpine:latest

RUN apk add --no-cache libgomp libgfortran

COPY --from=builder /grib2/aux_progs/gmerge /
COPY --from=builder /grib2/aux_progs/smallest_4 /
COPY --from=builder /grib2/aux_progs/smallest_grib2 /
COPY --from=builder /grib2/wgrib2/wgrib2 /

ENTRYPOINT [ "/wgrib2" ]
