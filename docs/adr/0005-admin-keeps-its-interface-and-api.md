# The admin keeps its interface and its API, with a backend in C++

The admin's interface in `admin/interface/` stays as it is, and its logic and state stay on the device. The backend is rewritten in C++ inside the kernel and serves the same HTTP and WebSocket API as the Python service, so the interface runs unchanged; it is ported module by module, with the Python tests in `admin/tests` as the specification it has to meet. It replaces BMNeXT's own web interface.

## Considered options

Moving the logic into the browser, with only a small API on the device, was rejected. The device has to validate everything it is sent anyway, a download must not depend on a browser tab staying open, and two browsers need one shared state.
