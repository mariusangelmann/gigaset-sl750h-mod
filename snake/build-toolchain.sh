#!/bin/bash
# Build a cr16-elf toolchain (binutils + gcc) on macOS for SL750H firmware mods.
# Requires: brew install gmp mpfr libmpc zlib
set -e
cd "$(dirname "$0")/../../.." 2>/dev/null || true
ROOT=${ROOT:-/tmp/cr16-toolchain}
mkdir -p "$ROOT" && cd "$ROOT"
PREFIX=$ROOT/prefix
JOBS=$(sysctl -n hw.ncpu)
HB=/opt/homebrew/opt
[ -d binutils-2.44 ] || { curl -sSLO https://ftp.gnu.org/gnu/binutils/binutils-2.44.tar.xz && tar xf binutils-2.44.tar.xz; }
[ -d gcc-14.3.0 ]   || { curl -sSLO https://ftp.gnu.org/gnu/gcc/gcc-14.3.0/gcc-14.3.0.tar.xz && tar xf gcc-14.3.0.tar.xz; }
mkdir -p bb bg
cd bb
[ -f Makefile ] || ../binutils-2.44/configure --target=cr16-elf --prefix=$PREFIX --disable-nls --disable-werror --with-system-zlib --without-zstd CPPFLAGS=-I$HB/zlib/include LDFLAGS=-L$HB/zlib/lib
make -j$JOBS && make install
cd ../bg
[ -f Makefile ] || ../gcc-14.3.0/configure --target=cr16-elf --prefix=$PREFIX --enable-languages=c --disable-multilib --disable-nls --without-headers --disable-libssp --disable-threads --disable-libgomp --disable-libmudflap --with-system-zlib --without-zstd --with-gmp=$HB/gmp --with-mpfr=$HB/mpfr --with-mpc=$HB/libmpc CPPFLAGS="-I$HB/zlib/include -I$HB/gmp/include -I$HB/mpfr/include -I$HB/libmpc/include" LDFLAGS="-L$HB/zlib/lib -L$HB/gmp/lib -L$HB/mpfr/lib -L$HB/libmpc/lib"
make -j$JOBS all-gcc all-target-libgcc && make install-gcc install-target-libgcc
echo "toolchain at $PREFIX/bin (cr16-elf-gcc -mcr16c)"
