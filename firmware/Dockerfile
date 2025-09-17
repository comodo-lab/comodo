# firmware/Dockerfile
FROM alpine:3.22 AS builder

RUN apk add --no-cache \
    build-base \
    git \
    make \
    python3 \
    readline-dev \
    readline-static \
    musl-dev \
    libc-dev \
    zlib-dev \
    zlib-static \
    ncurses-dev \
    ncurses-static

WORKDIR /src
RUN git clone --depth=1 https://github.com/micropython/micropython.git
WORKDIR /src/micropython
RUN git submodule update --init

RUN echo 'MICROPY_PY_BTREE = 0' >> ports/unix/mpconfigport.mk && \
    echo 'MICROPY_PY_FFI = 0' >> ports/unix/mpconfigport.mk

WORKDIR /src/micropython/ports/unix
RUN make -j$(nproc) \
    CFLAGS_EXTRA='-static -Wno-error=array-bounds' \
    LDFLAGS_EXTRA='-static' \
    STRIP=: \
    MICROPY_PY_BTREE=0

# Final image
FROM alpine:3.22
COPY --from=builder /src/micropython/ports/unix/build-standard/micropython /usr/local/bin/micropython

WORKDIR /sensor
COPY . .

CMD ["/usr/local/bin/micropython", "main.py"]
