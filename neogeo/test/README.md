# Tests

`t_io.py` drives the cart in Geolith (libretro) from Python with `neo.py`.
`neo.py` is the harness from MD3P_MVS: it simulates a quadrature spinner with
in-frame timing and can hold arbitrary port bits. It needs a Geolith core built
with that repo's `geolith-harness.patch`, plus a folder holding `neogeo.zip`:

```sh
GEOLITH_CORE=/path/to/geolith_libretro.so NEOGEO_SYSDIR=/path/to/sys python3 test/t_io.py
```
