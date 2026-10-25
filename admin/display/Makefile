# Builds pixel-exact.so, the library Previously loads into Previous so that
# its picture is shown by whole numbers. It links against the SDL3 of the
# system it is built on, so it is built in the Debian trixie the Pi runs.

CFLAGS ?= -O2
CFLAGS += -Wall -Wextra -Werror -fPIC $(shell pkg-config --cflags sdl3)
LDLIBS = $(shell pkg-config --libs sdl3) -ldl

pixel-exact.so: pixel-exact.c
	$(CC) $(CFLAGS) -shared -o $@ $< $(LDLIBS)

clean:
	rm -f pixel-exact.so

.PHONY: clean
