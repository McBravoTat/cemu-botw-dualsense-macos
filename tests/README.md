# Tests

Run `python3 -m unittest discover -s tests -v` without Cemu or a controller.
All input fixtures are synthetic; reference_packets.txt contains generated output commands.
Set RUN_EXPORTER_TESTS=1 on macOS to build and test the reader against export_fixture.cpp.
These checks do not establish live game/hardware compatibility.
